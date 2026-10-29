"""Folder-agnostic dataset discovery and ingestion."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from bpmn_adapt.domain.models import ProcessDefinition, ResourceFact, Rule, RuntimeState, TokenState


class FolderValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ProcessIdentity:
    """Content-bound identity that avoids same-name folder collisions."""

    process_id: str
    legacy_id: str
    canonical_folder: str
    source_checksums: tuple[str, ...]

    @classmethod
    def from_folder(cls, folder: str | Path, source_checksums: tuple[str, ...]):
        resolved = Path(folder).resolve()
        canonical = os.path.normcase(str(resolved))
        payload = json.dumps(
            {"folder": canonical, "sources": sorted(source_checksums)},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return cls(
            hashlib.sha256(payload).hexdigest()[:24],
            hashlib.sha256(resolved.name.encode("utf-8")).hexdigest()[:16],
            canonical,
            tuple(sorted(source_checksums)),
        )


@dataclass(frozen=True)
class ProcessBundle:
    definition: ProcessDefinition
    bpmn_xml: str
    rag_records: tuple[dict[str, str], ...]
    test_cases: tuple[dict[str, str], ...]
    remove_requests: str
    readd_request: str


REQUIRED = ("Rules.txt", "Resources.txt", "Remove_requests.txt", "Re_Add_Request.txt")
OUTPUT_TEXT = {"states.txt", "RagData.txt", "testcasees.txt"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="strict")


def _blocks(text: str, marker: str) -> tuple[dict[str, str], ...]:
    starts = list(re.finditer(rf"(?mi)^{re.escape(marker)}\s*([^:\n]*):?\s*(.*)$", text))
    records: list[dict[str, str]] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[match.start():end]
        fields: dict[str, str] = {"id": (match.group(1) or match.group(2)).strip()}
        for line in block.splitlines()[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip().lower().replace(" ", "_")] = value.strip()
        fields["text"] = block.strip()
        records.append(fields)
    return tuple(records)


def _states(text: str) -> tuple[RuntimeState, ...]:
    result: list[RuntimeState] = []
    for block in re.split(r"(?mi)(?=^STATE-[^:\n]+:)", text):
        head = re.search(r"(?mi)^(STATE-[^:\n]+):", block)
        if not head:
            continue
        position = re.search(r"(?mi)^Current process position:\s*(.+)$", block)
        completed = re.search(r"(?mi)^Completed activities:\s*(.+)$", block)
        current = position.group(1).strip() if position else "unknown"
        done = () if not completed or completed.group(1).strip().lower() == "none" else tuple(x.strip() for x in completed.group(1).split(","))
        result.append(RuntimeState(head.group(1), current, done, (TokenState(current),), {"source": block.strip()}))
    return tuple(result)


def ingest_folder(folder: str | Path) -> ProcessBundle:
    folder = Path(folder).resolve()
    if not folder.is_dir() or folder.name.startswith("."):
        raise FolderValidationError(f"Not a valid visible process folder: {folder}")
    missing = [name for name in REQUIRED if not (folder / name).is_file()]
    if missing:
        raise FolderValidationError(f"Missing required files: {', '.join(missing)}")
    bpmn_files = tuple(sorted(p for p in folder.iterdir() if p.is_file() and p.name.lower().endswith((".bpmn", ".bpmn2", ".bpmn2.xml", ".xml"))))
    if not bpmn_files:
        raise FolderValidationError("No BPMN model file found")
    excluded = set(REQUIRED) | OUTPUT_TEXT
    narrative_files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".txt" and p.name not in excluded and not p.name.lower().endswith(".quality.txt")]
    if not narrative_files:
        raise FolderValidationError("No narrative text file found")
    rules = tuple(Rule(f"R{n}", value.strip()) for n, value in re.findall(r"(?m)^\s*(\d+)\.\s*(.+)$", _read(folder / "Rules.txt")))
    resources = []
    for n, line in enumerate((x.strip() for x in _read(folder / "Resources.txt").splitlines() if x.strip()), 1):
        name, sep, value = line.partition(":")
        resources.append(ResourceFact(f"RES{n}", name.strip(), value.strip() if sep else line))
    states_path = folder / "states.txt"
    rag_path = folder / "RagData.txt"
    tests_path = folder / "testcasees.txt"
    source_checksums = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in bpmn_files)
    identity = ProcessIdentity.from_folder(folder, source_checksums)
    process_id = identity.process_id
    definition = ProcessDefinition(
        process_id=process_id, folder=folder, name=folder.name,
        narrative="\n\n".join(_read(p) for p in sorted(narrative_files)),
        bpmn_files=bpmn_files, rules=rules, resources=tuple(resources),
        states=_states(_read(states_path)) if states_path.exists() else (),
        metadata={
            "narrative_files": [p.name for p in narrative_files],
            "legacy_process_id": identity.legacy_id,
            "canonical_folder": identity.canonical_folder,
            "source_checksums": list(identity.source_checksums),
        },
    )
    return ProcessBundle(
        definition=definition, bpmn_xml=_read(bpmn_files[0]),
        rag_records=_blocks(_read(rag_path), "Example ID:") if rag_path.exists() else (),
        test_cases=_blocks(_read(tests_path), "Test case ID:") if tests_path.exists() else (),
        remove_requests=_read(folder / "Remove_requests.txt"),
        readd_request=_read(folder / "Re_Add_Request.txt"),
    )

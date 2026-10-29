"""Create a deterministic SHA-256 inventory of defense evidence and documents."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    destination = ROOT / "experiments" / "evidence" / "final" / "checksums.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    paths = [
        *sorted((ROOT / "experiments" / "evidence").glob("m*/**/task*-verification.json")),
        *sorted((ROOT / "experiments" / "evidence" / "m8" / "gui").glob("*.png")),
        ROOT / "experiments" / "evidence" / "m9" / "full-dataset" / "manifest-v2.jsonl",
        *sorted((ROOT / "docs").glob("*.md")),
        ROOT / "README.md",
        ROOT / "roadmap.md",
    ]
    entries = []
    for path in paths:
        if path.is_file() and path.resolve() != destination.resolve():
            entries.append({
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    payload = {"algorithm": "sha256", "entries": entries}
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

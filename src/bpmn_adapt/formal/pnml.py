"""Deterministic PNML normalization and checksumming."""
from __future__ import annotations

import hashlib
from pathlib import Path

from lxml import etree


def normalize_pnml(source: Path, target: Path) -> str:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True)
    root = etree.parse(str(source), parser).getroot()
    for parent in root.iter():
        children = list(parent)
        if children and all(_local(child) in {"place", "transition", "arc"} for child in children):
            children.sort(key=lambda item: (_local(item), item.get("id", "")))
            parent[:] = children
    data = etree.tostring(root, method="c14n", exclusive=False, with_comments=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _local(element) -> str:
    return element.tag.rsplit("}", 1)[-1]

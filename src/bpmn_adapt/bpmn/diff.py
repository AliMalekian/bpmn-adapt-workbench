"""Deterministic structural BPMN differ used by tests, reports, and metrics."""
from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET


_IGNORED_ATTRIBUTES = {"id"}


@dataclass(frozen=True)
class StructuralDiff:
    added_nodes: tuple[str, ...] = ()
    removed_nodes: tuple[str, ...] = ()
    added_flows: tuple[str, ...] = ()
    removed_flows: tuple[str, ...] = ()
    modified_elements: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not any((self.added_nodes, self.removed_nodes, self.added_flows,
                        self.removed_flows, self.modified_elements))


class BpmnDiffer:
    @staticmethod
    def compare(source_xml: str, target_xml: str) -> StructuralDiff:
        source = _elements(source_xml)
        target = _elements(target_xml)
        source_nodes = {key for key, value in source.items() if value[0] != "sequenceFlow"}
        target_nodes = {key for key, value in target.items() if value[0] != "sequenceFlow"}
        source_flows = set(source) - source_nodes
        target_flows = set(target) - target_nodes
        shared = set(source) & set(target)
        modified = tuple(sorted(key for key in shared if source[key] != target[key]))
        return StructuralDiff(
            tuple(sorted(target_nodes - source_nodes)),
            tuple(sorted(source_nodes - target_nodes)),
            tuple(sorted(target_flows - source_flows)),
            tuple(sorted(source_flows - target_flows)),
            modified,
        )


def _elements(xml: str) -> dict[str, tuple]:
    root = ET.fromstring(xml)
    result = {}
    for element in root.iter():
        element_id = element.get("id")
        kind = element.tag.rsplit("}", 1)[-1]
        if not element_id or kind in {"definitions", "process", "BPMNDiagram", "BPMNPlane",
                                     "BPMNShape", "BPMNEdge", "Bounds", "waypoint"}:
            continue
        attributes = tuple(sorted((key, value) for key, value in element.attrib.items()
                                  if key not in _IGNORED_ATTRIBUTES))
        children = tuple((child.tag.rsplit("}", 1)[-1], (child.text or "").strip())
                         for child in element)
        result[element_id] = (kind, attributes, children)
    return result

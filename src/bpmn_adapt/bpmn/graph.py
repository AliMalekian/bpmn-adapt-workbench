"""Minimal BPMN 2.0 graph that preserves the source XML tree."""
from __future__ import annotations

from dataclasses import dataclass
import copy
import re
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class BpmnNode:
    element_id: str
    name: str
    kind: str


@dataclass(frozen=True)
class BpmnFlow:
    element_id: str
    source_ref: str
    target_ref: str
    name: str = ""


class BpmnGraph:
    def __init__(self, root: ET.Element):
        self.root = root
        self.nodes: dict[str, BpmnNode] = {}
        self.flows: dict[str, BpmnFlow] = {}
        self.edges: set[tuple[str, str]] = set()
        self._refresh()

    @classmethod
    def from_xml(cls, xml: str) -> "BpmnGraph":
        return cls(ET.fromstring(xml))

    def clone(self) -> "BpmnGraph":
        return BpmnGraph(copy.deepcopy(self.root))

    def _refresh(self) -> None:
        self.nodes.clear(); self.flows.clear(); self.edges.clear()
        for element in self.root.iter():
            kind = element.tag.rsplit("}", 1)[-1]
            eid = element.get("id")
            if kind == "sequenceFlow":
                source, target = element.get("sourceRef"), element.get("targetRef")
                if eid and source and target:
                    self.flows[eid] = BpmnFlow(eid, source, target,
                                               element.get("name", ""))
                    self.edges.add((source, target))
            elif eid and kind not in {"definitions", "process", "collaboration", "participant", "lane", "laneSet"}:
                self.nodes[eid] = BpmnNode(eid, element.get("name", "") or kind, kind)

    def predecessors(self, element_id: str) -> tuple[str, ...]:
        return tuple(sorted(a for a, b in self.edges if b == element_id))

    def successors(self, element_id: str) -> tuple[str, ...]:
        return tuple(sorted(b for a, b in self.edges if a == element_id))

    def element_by_name(self, name: str) -> BpmnNode | None:
        lowered = name.casefold().strip()
        return next((node for node in self.nodes.values() if node.name.casefold().strip() == lowered), None)

    def resolve_node(self, reference: str) -> BpmnNode | None:
        """Resolve an ID, exact name, or natural-language reference safely."""
        direct=self.nodes.get(reference) or self.element_by_name(reference)
        if direct: return direct
        text=reference.casefold()
        candidates=[]
        stop={"the","a","an","to","of","and","or","please","remove","delete","restore","re-add","activity","task","element","step"}
        ref_tokens={x for x in re.findall(r"[\w-]+",text) if x not in stop}
        for node in self.nodes.values():
            name=node.name.casefold().strip()
            if name and name in text: score=1.0
            else:
                node_tokens={x for x in re.findall(r"[\w-]+",name) if x not in stop}
                score=len(ref_tokens & node_tokens)/len(node_tokens) if node_tokens else 0.0
            candidates.append((score,node.name,node))
        candidates.sort(key=lambda row:(-row[0],row[1]))
        return candidates[0][2] if candidates and candidates[0][0]>=0.5 else None

    def to_xml(self) -> str:
        return ET.tostring(self.root, encoding="unicode")

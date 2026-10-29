"""Versioned semantic BPMN rules beyond what XML Schema can express."""
from __future__ import annotations

from collections import Counter, deque
from lxml import etree

from bpmn_adapt.domain.validation import DiagnosticSeverity, ValidationDiagnostic


SEMANTIC_RULESET_VERSION = "1.0.0"
MODEL_NAMESPACE = "http://www.omg.org/spec/BPMN/20100524/MODEL"
ACTIVITY_TYPES = {
    "task", "userTask", "serviceTask", "manualTask", "scriptTask",
    "businessRuleTask", "sendTask", "receiveTask", "callActivity", "subProcess",
}
UNSUPPORTED_EXECUTABLE = {
    "complexGateway", "eventBasedGateway", "adHocSubProcess", "transaction",
    "choreographyTask", "callChoreography",
}


class SemanticBpmnValidator:
    validator_id = "bpmn-semantic-rules"
    validator_version = SEMANTIC_RULESET_VERSION

    def validate(self, root: etree._Element, executable_required: bool = True):
        diagnostics: list[ValidationDiagnostic] = []
        elements = [item for item in root.iter()
                    if item.get("id") and _namespace(item) == MODEL_NAMESPACE]
        ids = [str(item.get("id")) for item in elements]
        duplicate_ids = sorted(key for key, count in Counter(ids).items() if count > 1)
        if duplicate_ids:
            diagnostics.append(_error("SEM_DUPLICATE_ID", "Duplicate BPMN IDs", duplicate_ids))
        by_id = {str(item.get("id")): item for item in elements}
        flows = [item for item in elements if _local(item) == "sequenceFlow"]

        for flow in flows:
            flow_id = str(flow.get("id"))
            source_ref, target_ref = flow.get("sourceRef"), flow.get("targetRef")
            missing = tuple(ref for ref in (source_ref, target_ref) if ref not in by_id)
            if missing:
                diagnostics.append(_error("SEM_BROKEN_REFERENCE",
                                          f"Flow {flow_id} references missing elements",
                                          (flow_id, *missing)))
                continue
            source_kind, target_kind = _local(by_id[source_ref]), _local(by_id[target_ref])
            if source_kind == "endEvent" or target_kind == "startEvent" \
                    or source_kind == "sequenceFlow" or target_kind == "sequenceFlow":
                diagnostics.append(_error("SEM_ILLEGAL_FLOW_ENDPOINT",
                                          f"Illegal endpoints for flow {flow_id}",
                                          (flow_id, source_ref, target_ref)))

        for element in elements:
            kind, element_id = _local(element), str(element.get("id"))
            default = element.get("default")
            if default is not None and "Gateway" in kind:
                flow = by_id.get(default)
                if flow is None or _local(flow) != "sequenceFlow" \
                        or flow.get("sourceRef") != element_id:
                    diagnostics.append(_error("SEM_GATEWAY_DEFAULT",
                                              f"Gateway {element_id} default is not an outgoing flow",
                                              (element_id, default)))
            if kind == "boundaryEvent":
                attached = element.get("attachedToRef")
                if attached not in by_id or _local(by_id[attached]) not in ACTIVITY_TYPES:
                    diagnostics.append(_error("SEM_BOUNDARY_SCOPE",
                                              f"Boundary event {element_id} is not attached to an activity",
                                              (element_id, *((attached,) if attached else ()))))

        diagnostics.extend(self._reachability(elements, flows, by_id))
        if executable_required:
            unsupported = tuple(sorted(str(item.get("id")) for item in elements
                                       if _local(item) in UNSUPPORTED_EXECUTABLE))
            if unsupported:
                diagnostics.append(ValidationDiagnostic(
                    "SEM_EXECUTABLE_UNSUPPORTED", DiagnosticSeverity.ERROR,
                    "Model uses constructs not supported by the executable subset", unsupported))
        return tuple(diagnostics)

    @staticmethod
    def _reachability(elements, flows, by_id):
        starts = [str(item.get("id")) for item in elements if _local(item) == "startEvent"]
        adjacency: dict[str, list[str]] = {}
        for flow in flows:
            if flow.get("sourceRef") in by_id and flow.get("targetRef") in by_id:
                adjacency.setdefault(str(flow.get("sourceRef")), []).append(str(flow.get("targetRef")))
        reached, queue = set(starts), deque(starts)
        while queue:
            for target in adjacency.get(queue.popleft(), ()):
                if target not in reached:
                    reached.add(target); queue.append(target)
        unreachable = []
        for item in elements:
            kind, element_id = _local(item), str(item.get("id"))
            if kind in {"definitions", "sequenceFlow", "process", "collaboration",
                        "participant", "lane", "laneSet"}:
                continue
            if kind == "boundaryEvent" and item.get("attachedToRef") in reached:
                continue
            if element_id not in reached:
                unreachable.append(element_id)
        return (() if not unreachable else (
            _error("SEM_UNREACHABLE_NODE", "Nodes are unreachable from a start event",
                   tuple(sorted(unreachable))),))


def _local(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _namespace(element) -> str:
    return element.tag[1:].split("}", 1)[0] if element.tag.startswith("{") else ""


def _error(code: str, message: str, ids) -> ValidationDiagnostic:
    return ValidationDiagnostic(code, DiagnosticSeverity.ERROR, message, tuple(ids),
                                "OMG BPMN 2.0.2 semantic constraints")

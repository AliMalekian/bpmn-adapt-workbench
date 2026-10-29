"""Transactional, typed BPMN graph mutation and runtime-state migration."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from typing import Any

from bpmn_adapt.bpmn.changes import ChangeAction, ChangeOperation, ChangeSet, ElementSubject
from bpmn_adapt.bpmn.diff import BpmnDiffer, StructuralDiff
from bpmn_adapt.bpmn.graph import BpmnGraph
from bpmn_adapt.domain.models import AtomicChange, MigrationPlan, OperationType, RuntimeState, TokenState

MODEL_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"


class UnsafeMutation(ValueError):
    """Raised when an operation cannot be applied without unsafe state loss."""


@dataclass(frozen=True)
class MutationResult:
    xml: str
    inverse: ChangeSet
    diff: StructuralDiff
    migration: MigrationPlan
    diagnostics: tuple[dict[str, Any], ...]
    source_checksum: str
    result_checksum: str
    applied_operations: tuple[ChangeOperation, ...]

    @property
    def graph(self) -> BpmnGraph:
        return BpmnGraph.from_xml(self.xml)


@dataclass(frozen=True)
class LegacyMutationResult:
    graph: BpmnGraph
    change: AtomicChange
    migration: MigrationPlan


class MutationEngine:
    """Apply a complete ChangeSet atomically to a private XML tree."""

    ALLOWED_NODE_TYPES = frozenset({
        "task", "userTask", "serviceTask", "manualTask", "scriptTask",
        "businessRuleTask", "sendTask", "receiveTask", "callActivity",
        "subProcess", "startEvent", "endEvent", "intermediateCatchEvent",
        "intermediateThrowEvent", "boundaryEvent", "exclusiveGateway",
        "inclusiveGateway", "parallelGateway", "eventBasedGateway", "complexGateway",
    })

    @staticmethod
    def checksum(xml: str) -> str:
        return hashlib.sha256(xml.encode("utf-8")).hexdigest()

    def apply(self, xml: str, changes: ChangeSet, runtime: RuntimeState) -> MutationResult:
        _register_namespaces(xml)
        source_checksum = self.checksum(xml)
        root = ET.fromstring(xml)
        inverse_operations: list[ChangeOperation] = []
        applied: list[ChangeOperation] = []
        token_mappings: dict[str, str] = {}
        diagnostics: list[dict[str, Any]] = []

        for index, original in enumerate(changes.operations):
            operation = original
            if operation.action is ChangeAction.ADD and not operation.target_id:
                operation = replace(operation, target_id=self._stable_id(source_checksum, index, operation))
            operation.validate()
            generated_inverse, generated_mappings, generated_diagnostics = self._apply_one(
                root, operation, runtime)
            inverse_operations = generated_inverse + inverse_operations
            token_mappings.update(generated_mappings)
            diagnostics.extend(generated_diagnostics)
            applied.append(operation)

        result_xml = ET.tostring(root, encoding="unicode")
        variables = runtime.context.get("variables")
        if not isinstance(variables, dict):
            variables = {key: value for key, value in runtime.context.items()
                         if key != "scopes"}
        scopes = runtime.context.get("scopes", {})
        variable_mappings = ({str(key): str(key) for key in variables}
                             if isinstance(variables, dict) else {})
        scope_mappings = ({str(key): str(key) for key in scopes}
                          if isinstance(scopes, dict) else {})
        migration = MigrationPlan(
            token_mappings, True,
            "Every active removed element has a deterministic target; unchanged tokens remain in place.",
            variable_mappings, scope_mappings,
        )
        return MutationResult(
            result_xml, ChangeSet(tuple(inverse_operations)), BpmnDiffer.compare(xml, result_xml),
            migration, tuple(diagnostics), source_checksum, self.checksum(result_xml), tuple(applied),
        )

    def _apply_one(self, root: ET.Element, operation: ChangeOperation, runtime: RuntimeState):
        if operation.action is ChangeAction.ADD:
            return self._add(root, operation)
        if operation.action is ChangeAction.RE_ADD:
            return self._re_add(root, operation)
        if operation.action is ChangeAction.MODIFY:
            return self._modify(root, operation)
        if operation.action is ChangeAction.REMOVE:
            return self._remove(root, operation, runtime)
        raise UnsafeMutation(f"Unsupported action: {operation.action.value}")

    def _add(self, root: ET.Element, operation: ChangeOperation):
        assert operation.target_id
        if _find_by_id(root, operation.target_id) is not None:
            raise UnsafeMutation(f"BPMN element already exists: {operation.target_id}")
        process = _process(root, operation.parent_id)
        if operation.subject is ElementSubject.NODE:
            if operation.element_type not in self.ALLOWED_NODE_TYPES:
                raise UnsafeMutation(f"Unsupported BPMN node type: {operation.element_type}")
            element = ET.SubElement(process, _qualified(process, operation.element_type),
                                    {"id": operation.target_id})
            self._set_attributes(element, operation.attributes)
            self._add_di_shape(root, operation.target_id)
        else:
            if _find_by_id(root, operation.source_ref) is None or _find_by_id(root, operation.target_ref) is None:
                raise UnsafeMutation("ADD FLOW endpoints must already exist")
            element = ET.SubElement(process, _qualified(process, "sequenceFlow"), {
                "id": operation.target_id, "sourceRef": str(operation.source_ref),
                "targetRef": str(operation.target_ref),
            })
            self._set_attributes(element, operation.attributes)
            self._set_condition(element, operation.condition_expression, operation.clear_condition)
        inverse = ChangeOperation(ChangeAction.REMOVE, operation.subject, operation.target_id)
        return [inverse], {}, ({"code": "ELEMENT_ADDED", "element_id": operation.target_id},)

    def _re_add(self, root: ET.Element, operation: ChangeOperation):
        assert operation.target_id and operation.xml_fragment
        if _find_by_id(root, operation.target_id) is not None:
            raise UnsafeMutation(f"BPMN element already exists: {operation.target_id}")
        parent = _process(root, operation.parent_id)
        parent.append(_parse_xml_fragment(operation.xml_fragment))
        if operation.subject is ElementSubject.NODE:
            self._add_di_shape(root, operation.target_id)
        inverse = ChangeOperation(ChangeAction.REMOVE, operation.subject, operation.target_id)
        return [inverse], {}, ({"code": "ELEMENT_RESTORED", "element_id": operation.target_id},)

    def _modify(self, root: ET.Element, operation: ChangeOperation):
        assert operation.target_id
        element = _find_by_id(root, operation.target_id)
        if element is None:
            raise UnsafeMutation(f"Unknown BPMN element: {operation.target_id}")
        actual = ElementSubject.FLOW if _local(element.tag) == "sequenceFlow" else ElementSubject.NODE
        if actual is not operation.subject:
            raise UnsafeMutation(f"Element subject mismatch for {operation.target_id}")
        old_type = _local(element.tag)
        old_attributes = {name: element.get(name) for name in operation.attributes}
        old_condition = _condition(element)
        if operation.element_type:
            if operation.subject is ElementSubject.FLOW:
                raise UnsafeMutation("A sequence flow cannot be changed into a node")
            if operation.element_type not in self.ALLOWED_NODE_TYPES:
                raise UnsafeMutation(f"Unsupported BPMN node type: {operation.element_type}")
            element.tag = _qualified(element, operation.element_type)
        self._set_attributes(element, operation.attributes)
        if operation.subject is ElementSubject.FLOW:
            self._set_condition(element, operation.condition_expression, operation.clear_condition)
        inverse = ChangeOperation(
            ChangeAction.MODIFY, operation.subject, operation.target_id,
            old_type if operation.element_type else None, old_attributes,
            condition_expression=old_condition,
            clear_condition=old_condition is None and (
                operation.condition_expression is not None or operation.clear_condition),
        )
        return [inverse], {}, ({"code": "ELEMENT_MODIFIED", "element_id": operation.target_id},)

    def _remove(self, root: ET.Element, operation: ChangeOperation, runtime: RuntimeState):
        assert operation.target_id
        element = _find_by_id(root, operation.target_id)
        if element is None:
            raise UnsafeMutation(f"Unknown BPMN element: {operation.target_id}")
        actual = ElementSubject.FLOW if _local(element.tag) == "sequenceFlow" else ElementSubject.NODE
        if actual is not operation.subject:
            raise UnsafeMutation(f"Element subject mismatch for {operation.target_id}")
        if operation.subject is ElementSubject.FLOW:
            parent = _parent_map(root)[element]
            fragment = ET.tostring(element, encoding="unicode")
            parent_id = parent.get("id")
            parent.remove(element)
            inverse = ChangeOperation(ChangeAction.RE_ADD, ElementSubject.FLOW, operation.target_id,
                                      parent_id=parent_id, xml_fragment=fragment)
            return [inverse], {}, ({"code": "FLOW_REMOVED", "element_id": operation.target_id},)
        return self._remove_node(root, element, operation, runtime)

    def _remove_node(self, root: ET.Element, element: ET.Element,
                     operation: ChangeOperation, runtime: RuntimeState):
        target_id = str(operation.target_id)
        graph = BpmnGraph(root)
        predecessors, successors = graph.predecessors(target_id), graph.successors(target_id)
        active_ids = {token.element_id for token in runtime.tokens if token.status == "active"}
        if runtime.current_position:
            active_ids.add(runtime.current_position)
        token_mappings: dict[str, str] = {}
        if target_id in active_ids:
            if len(successors) != 1:
                raise UnsafeMutation(
                    f"active element {target_id} is unmappable: expected one successor, got {len(successors)}")
            token_mappings[target_id] = successors[0]

        parents = _parent_map(root)
        parent = parents[element]
        parent_id = parent.get("id")
        node_fragment = ET.tostring(element, encoding="unicode")
        connected = [item for item in root.iter() if _local(item.tag) == "sequenceFlow"
                     and (item.get("sourceRef") == target_id or item.get("targetRef") == target_id)]
        flow_snapshots = [(str(item.get("id")), parents[item].get("id"),
                           ET.tostring(item, encoding="unicode")) for item in connected]
        for item in connected:
            parents[item].remove(item)
        parent.remove(element)
        self._remove_di(root, target_id)

        bypass_ids: list[str] = []
        process = _process(root, parent_id)
        existing_ids = {item.get("id") for item in root.iter() if item.get("id")}
        for source in predecessors:
            for target in successors:
                base, counter = f"adapt_{source}_{target}", 2
                bypass_id = base
                while bypass_id in existing_ids:
                    bypass_id, counter = f"{base}_{counter}", counter + 1
                ET.SubElement(process, _qualified(process, "sequenceFlow"), {
                    "id": bypass_id, "sourceRef": source, "targetRef": target})
                existing_ids.add(bypass_id)
                bypass_ids.append(bypass_id)

        inverse: list[ChangeOperation] = [
            ChangeOperation(ChangeAction.REMOVE, ElementSubject.FLOW, bypass_id)
            for bypass_id in bypass_ids]
        inverse.append(ChangeOperation(ChangeAction.RE_ADD, ElementSubject.NODE, target_id,
                                       parent_id=parent_id, xml_fragment=node_fragment))
        inverse.extend(ChangeOperation(ChangeAction.RE_ADD, ElementSubject.FLOW, flow_id,
                                       parent_id=flow_parent, xml_fragment=fragment)
                       for flow_id, flow_parent, fragment in flow_snapshots)
        return inverse, token_mappings, ({"code": "NODE_REMOVED", "element_id": target_id,
                                          "bypass_flows": bypass_ids},)

    @staticmethod
    def _set_attributes(element: ET.Element, attributes: dict[str, Any]) -> None:
        if "id" in attributes:
            raise UnsafeMutation("Element IDs cannot be modified")
        for name, value in attributes.items():
            if value is None:
                element.attrib.pop(str(name), None)
            else:
                element.set(str(name), str(value))

    @staticmethod
    def _set_condition(flow: ET.Element, expression: str | None, clear: bool) -> None:
        conditions = [child for child in flow if _local(child.tag) == "conditionExpression"]
        if clear:
            for child in conditions:
                flow.remove(child)
        if expression is not None:
            for child in list(flow):
                if _local(child.tag) == "conditionExpression":
                    flow.remove(child)
            child = ET.SubElement(flow, _qualified(flow, "conditionExpression"))
            child.text = expression

    @staticmethod
    def _stable_id(source_checksum: str, index: int, operation: ChangeOperation) -> str:
        canonical = json.dumps(operation.to_dict(), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(f"{source_checksum}:{index}:{canonical}".encode()).hexdigest()[:10]
        kind = operation.element_type or operation.subject.value.lower()
        return f"adapt_{kind}_{digest}"

    @staticmethod
    def _add_di_shape(root: ET.Element, target_id: str) -> None:
        plane = next((item for item in root.iter() if _local(item.tag) == "BPMNPlane"), None)
        if plane is None or _find_by_id(root, f"{target_id}_di") is not None:
            return
        shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape",
                              {"id": f"{target_id}_di", "bpmnElement": target_id})
        ET.SubElement(shape, f"{{{DC_NS}}}Bounds",
                      {"x": "0", "y": "0", "width": "100", "height": "80"})

    @staticmethod
    def _remove_di(root: ET.Element, target_id: str) -> None:
        parents = _parent_map(root)
        for item in list(root.iter()):
            if item.get("bpmnElement") == target_id and item in parents:
                parents[item].remove(item)


def remove_element(graph: BpmnGraph, target_id: str, active_tokens: set[str]) -> LegacyMutationResult:
    """Backwards-compatible single-node REMOVE facade."""
    if target_id not in graph.nodes:
        raise UnsafeMutation(f"Unknown BPMN element: {target_id}")
    node = graph.nodes[target_id]
    if "Gateway" in node.kind or node.kind.endswith("Event"):
        raise UnsafeMutation(
            f"Removing {node.kind} through the legacy facade requires an explicit typed rewrite")
    runtime = RuntimeState("legacy", next(iter(active_tokens), ""), (),
                           tuple(TokenState(item) for item in sorted(active_tokens)))
    result = MutationEngine().apply(
        graph.to_xml(), ChangeSet((ChangeOperation(ChangeAction.REMOVE,
                                                    ElementSubject.NODE, target_id),)), runtime)
    change = AtomicChange(OperationType.REMOVE, target_id, node.name,
                          graph.predecessors(target_id), graph.successors(target_id))
    return LegacyMutationResult(result.graph, change, result.migration)


def _parse_xml_fragment(fragment: str) -> ET.Element:
    """Safely parses an XML fragment even if it uses bpmn:, bpmndi:, dc:, or camunda: prefixes."""
    frag = fragment.strip()
    try:
        return ET.fromstring(frag)
    except (ET.ParseError, ValueError) as err:
        if "unbound prefix" in str(err).lower() or "namespace" in str(err).lower():
            wrapper = (
                '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
                'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
                'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
                'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
                'xmlns:camunda="http://camunda.org/schema/1.0/bpmn" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">\n'
                f"{frag}\n"
                '</bpmn:definitions>'
            )
            wrapped_elem = ET.fromstring(wrapper)
            if len(wrapped_elem) > 0:
                return wrapped_elem[0]
        raise


def _register_namespaces(xml: str) -> None:
    try:
        for _, (prefix, uri) in ET.iterparse(io.StringIO(xml), events=("start-ns",)):
            if prefix != "xml":
                ET.register_namespace(prefix or "", uri)
    except (ET.ParseError, ValueError):
        pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(element: ET.Element) -> str:
    return element.tag[1:].split("}", 1)[0] if element.tag.startswith("{") else ""


def _qualified(element: ET.Element, local: str) -> str:
    return f"{{{_namespace(element) or MODEL_NS}}}{local}"


def _find_by_id(root: ET.Element, element_id: str | None) -> ET.Element | None:
    if element_id is None:
        return None
    return next((item for item in root.iter() if item.get("id") == element_id), None)


def _parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


def _process(root: ET.Element, parent_id: str | None = None) -> ET.Element:
    if parent_id:
        parent = _find_by_id(root, parent_id)
        if parent is None:
            raise UnsafeMutation(f"Unknown parent element: {parent_id}")
        return parent
    process = next((item for item in root.iter() if _local(item.tag) == "process"), None)
    if process is None:
        raise UnsafeMutation("BPMN document has no process")
    return process


def _condition(flow: ET.Element) -> str | None:
    child = next((item for item in flow if _local(item.tag) == "conditionExpression"), None)
    return None if child is None else (child.text or "")

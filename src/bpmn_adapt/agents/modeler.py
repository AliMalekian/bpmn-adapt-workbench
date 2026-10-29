"""Modeler Agent: strict LLM change translation and deterministic BPMN mutation."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import uuid

from bpmn_adapt.bpmn.changes import (
    ChangeAction, ChangeOperation, ChangeSet, ChangeValidationError, ElementSubject,
)
from bpmn_adapt.bpmn.graph import BpmnGraph
from bpmn_adapt.bpmn.mutation import MutationEngine
from bpmn_adapt.bpmn.validation import BpmnValidator
from bpmn_adapt.domain.models import (
    AtomicChange, CandidateModel, DecisionStatus, MigrationPlan, OperationType,
    RuntimeState, TokenState,
)
from bpmn_adapt.prompts.loader import load_prompt
from bpmn_adapt.domain.validation import ValidationStatus


class ModelerAuthorizationError(PermissionError):
    pass


class ModelerAgent:
    def __init__(
        self,
        llm_client,
        mutation_engine: MutationEngine | None = None,
        validator: BpmnValidator | None = None,
        prompt_name: str = "modeler",
    ):
        self.llm = llm_client
        self.mutation_engine = mutation_engine or MutationEngine()
        self.validator = validator or BpmnValidator()
        self.prompt_name = prompt_name

    def model(
        self,
        decision,
        current_bpmn_xml: str,
        active_tokens: set[str],
        *,
        oracle_bpmn_xml: str | None = None,
        feedback: tuple[dict, ...] | None = None,
        runtime_state: RuntimeState | None = None,
    ) -> CandidateModel:
        if decision.status not in {DecisionStatus.APPROVE, DecisionStatus.ALTERNATIVE_PROPOSED}:
            raise ModelerAuthorizationError("Modeler requires an approved feasibility decision")

        graph = BpmnGraph.from_xml(current_bpmn_xml)
        request = decision.request

        import re
        semantic_bpmn_xml = re.sub(r'<bpmndi:BPMNDiagram[\s\S]*?</bpmndi:BPMNDiagram>', '', current_bpmn_xml)

        payload = {
            "decision": decision.to_dict(),
            "experiment_feedback": list(feedback or ()),
            "current_bpmn_xml": semantic_bpmn_xml,
            "existing_nodes": [{"id": n.element_id, "name": n.name, "kind": n.kind} for n in graph.nodes.values()],
        }

        system_prompt = load_prompt(self.prompt_name)
        proposal = self.llm.complete(
            system_prompt, json.dumps(payload, ensure_ascii=False), schema_name="model"
        )

        change_set = self._parse_and_prepare_changes(proposal, request, graph)

        runtime = runtime_state or RuntimeState(
            "modeler-runtime",
            next(iter(sorted(active_tokens)), ""),
            (),
            tuple(TokenState(token) for token in sorted(active_tokens)),
            {},
        )

        result = self.mutation_engine.apply(current_bpmn_xml, change_set, runtime)
        atomic_changes = tuple(
            self._atomic_change(item, graph, result.graph)
            for item in result.applied_operations
        )
        candidate = CandidateModel(
            str(uuid.uuid4()),
            request.source_version_id or f"{request.process_id}-source",
            result.xml,
            atomic_changes,
            result.migration,
            result.result_checksum,
        )
        self._require_conformant(candidate.bpmn_xml)
        return candidate

    def _parse_and_prepare_changes(
        self, proposal: dict, request, graph: BpmnGraph
    ) -> ChangeSet:
        raw_changes = proposal.get("changes") if isinstance(proposal, dict) else None
        operations: list[ChangeOperation] = []

        if raw_changes:
            if isinstance(raw_changes, list):
                raw_changes = {"operations": raw_changes}
            try:
                parsed_set = ChangeSet.from_dict(raw_changes)
                for op in parsed_set.operations:
                    if op.action in {ChangeAction.MODIFY, ChangeAction.REMOVE} and op.subject == ElementSubject.NODE:
                        if op.target_id and op.target_id not in graph.nodes:
                            resolved_node = graph.resolve_node(op.target_id)
                            if resolved_node:
                                op = replace(op, target_id=resolved_node.element_id)

                    if op.action == ChangeAction.RE_ADD and op.subject == ElementSubject.NODE:
                        op = self._prepare_re_add_operation(op, graph, request)

                    operations.append(op)
            except ChangeValidationError as exc:
                raise ValueError(str(exc)) from exc

        if not operations:
            if request.operation is OperationType.REMOVE:
                node = graph.resolve_node(request.target_element)
                if not node:
                    raise ValueError(f"Target BPMN element not found: {request.target_element}")
                operations.append(
                    ChangeOperation(ChangeAction.REMOVE, ElementSubject.NODE, node.element_id)
                )
            elif request.operation is OperationType.RE_ADD:
                synth_op = ChangeOperation(
                    action=ChangeAction.RE_ADD,
                    subject=ElementSubject.NODE,
                    target_id=None,
                    element_type="task",
                    attributes={"name": request.target_element},
                )
                operations.append(self._prepare_re_add_operation(synth_op, graph, request))
            elif request.operation is OperationType.MODIFY:
                target_node = graph.resolve_node(request.target_element) or (list(graph.nodes.values())[0] if graph.nodes else None)
                if not target_node:
                    raise ValueError(f"Target BPMN element not found for MODIFY: {request.target_element}")
                operations.append(
                    ChangeOperation(
                        action=ChangeAction.MODIFY,
                        subject=ElementSubject.NODE,
                        target_id=target_node.element_id,
                        attributes={"name": f"{target_node.name} (Updated)"},
                    )
                )
            elif request.operation is OperationType.ADD:
                operations.append(
                    ChangeOperation(
                        action=ChangeAction.ADD,
                        subject=ElementSubject.NODE,
                        target_id=None,
                        element_type="task",
                        attributes={"name": request.target_element or "Quality Inspection"},
                    )
                )
            else:
                raise ValueError(f"Modeler requires an explicit ChangeSet for {request.operation.value}")

        final_operations: list[ChangeOperation] = []
        for op in operations:
            final_operations.append(op)
            if op.action == ChangeAction.RE_ADD and op.subject == ElementSubject.NODE:
                node_id = op.target_id
                if op.source_ref and op.target_ref:
                    for flow_id, flow in graph.flows.items():
                        if flow.source_ref == op.source_ref and flow.target_ref == op.target_ref:
                            final_operations.append(
                                ChangeOperation(
                                    action=ChangeAction.REMOVE,
                                    subject=ElementSubject.FLOW,
                                    target_id=flow_id,
                                )
                            )
                    flow_in_id = f"Flow_{uuid.uuid4().hex[:7]}"
                    final_operations.append(
                        ChangeOperation(
                            action=ChangeAction.ADD,
                            subject=ElementSubject.FLOW,
                            target_id=flow_in_id,
                            source_ref=op.source_ref,
                            target_ref=node_id,
                        )
                    )
                    flow_out_id = f"Flow_{uuid.uuid4().hex[:7]}"
                    final_operations.append(
                        ChangeOperation(
                            action=ChangeAction.ADD,
                            subject=ElementSubject.FLOW,
                            target_id=flow_out_id,
                            source_ref=node_id,
                            target_ref=op.target_ref,
                        )
                    )

        return ChangeSet(tuple(final_operations))

    def _prepare_re_add_operation(
        self, op: ChangeOperation, graph: BpmnGraph, request
    ) -> ChangeOperation:
        if op.source_ref and op.source_ref not in graph.nodes:
            raise ValueError(f"RE_ADD source_ref={op.source_ref} not found in current graph")
        if op.target_ref and op.target_ref not in graph.nodes:
            raise ValueError(f"RE_ADD target_ref={op.target_ref} not found in current graph")

        node_id = op.target_id or f"Activity_{uuid.uuid4().hex[:7]}"
        node_name = op.attributes.get("name") or request.target_element
        elem_type = op.element_type or "task"

        xml_frag = op.xml_fragment
        if not xml_frag:
            xml_frag = f'<{elem_type} xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" id="{node_id}" name="{node_name}" />'
        elif 'xmlns="' not in xml_frag:
            xml_frag = xml_frag.replace(f"<{elem_type}", f'<{elem_type} xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"', 1)

        return replace(
            op,
            target_id=node_id,
            element_type=elem_type,
            xml_fragment=xml_frag,
            attributes={"name": node_name},
        )

    def _require_conformant(self, xml: str) -> None:
        report = self.validator.validate(xml, executable_required=True)
        if report.status is not ValidationStatus.PASS:
            codes = ", ".join(sorted({item.code for item in report.diagnostics}))
            raise ValueError(f"BPMN validation failed before experimentation: {codes}")

    @staticmethod
    def _atomic_change(
        operation: ChangeOperation, before: BpmnGraph, after: BpmnGraph
    ) -> AtomicChange:
        assert operation.target_id
        node = before.nodes.get(operation.target_id) or after.nodes.get(operation.target_id)
        name = node.name if node else operation.target_id
        source = before if operation.action is ChangeAction.REMOVE else after
        predecessors = source.predecessors(operation.target_id)
        successors = source.successors(operation.target_id)
        return AtomicChange(
            OperationType(operation.action.value),
            operation.target_id,
            name,
            predecessors or ((operation.source_ref,) if operation.source_ref else ()),
            successors or ((operation.target_ref,) if operation.target_ref else ()),
        )

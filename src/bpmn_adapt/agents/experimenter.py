"""Experimenter Agent: hybrid deterministic simulation and LLM semantic evaluation with deterministic veto."""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any
import uuid

from bpmn_adapt.bpmn.graph import BpmnGraph
from bpmn_adapt.bpmn.validation import BpmnValidator
from bpmn_adapt.domain.models import CandidateModel, ExperimentReport, OperationType
from bpmn_adapt.domain.validation import ValidationStatus
from bpmn_adapt.prompts.loader import load_prompt
from bpmn_adapt.simulation.engine import simulate

logger = logging.getLogger(__name__)


class ExperimenterAgent:
    def __init__(
        self,
        llm_client,
        *,
        formal_verifier=None,
        formal_output_root: Path | str = "experiments/formal",
        validator: BpmnValidator | None = None,
        prompt_name: str = "experimenter",
    ):
        self.llm = llm_client
        self.formal_verifier = formal_verifier
        self.formal_output_root = Path(formal_output_root)
        self.validator = validator or BpmnValidator()
        self.prompt_name = prompt_name

    def experiment(
        self,
        candidate: CandidateModel,
        original_bpmn_xml: str | None = None,
        operation: OperationType | None = None,
    ) -> ExperimentReport:
        graph = BpmnGraph.from_xml(candidate.bpmn_xml)
        failures: list[dict[str, Any]] = []

        # 1. Deterministic Token Migration Validation
        for old, new in candidate.migration.mappings.items():
            if new not in graph.nodes:
                failures.append({
                    "type": "invalid_token_migration",
                    "source": old,
                    "target": new,
                })

        # 2. Deterministic Orphaned-Node Detection
        for node in graph.nodes.values():
            preds = graph.predecessors(node.element_id)
            succs = graph.successors(node.element_id)
            if node.kind == "startEvent":
                if not succs:
                    failures.append({
                        "type": "orphaned_node",
                        "node_id": node.element_id,
                        "kind": node.kind,
                        "reason": "startEvent has no outgoing flows",
                    })
            elif node.kind == "endEvent":
                if not preds:
                    failures.append({
                        "type": "orphaned_node",
                        "node_id": node.element_id,
                        "kind": node.kind,
                        "reason": "endEvent has no incoming flows",
                    })
            elif node.kind in {"boundaryEvent", "intermediateCatchEvent"}:
                if not succs:
                    failures.append({
                        "type": "orphaned_node",
                        "node_id": node.element_id,
                        "kind": node.kind,
                        "reason": f"{node.kind} has no outgoing flows",
                    })
            elif node.kind in {"textAnnotation", "association"}:
                continue
            else:
                if not preds:
                    failures.append({
                        "type": "orphaned_node",
                        "node_id": node.element_id,
                        "kind": node.kind,
                        "reason": f"Node {node.element_id} ({node.name}) has no incoming flows",
                    })
                if not succs:
                    failures.append({
                        "type": "orphaned_node",
                        "node_id": node.element_id,
                        "kind": node.kind,
                        "reason": f"Node {node.element_id} ({node.name}) has no outgoing flows",
                    })

        # 3. Deterministic BPMN Conformance Validation
        try:
            val_report = self.validator.validate(candidate.bpmn_xml, executable_required=True)
            if val_report.status is not ValidationStatus.PASS:
                for d in val_report.diagnostics:
                    failures.append({
                        "type": "bpmn_validation",
                        "code": d.code,
                        "message": d.message,
                    })
        except Exception as exc:
            failures.append({
                "type": "bpmn_validation_exception",
                "message": str(exc),
            })

        # 4. Deterministic Simulation Execution
        traces, simulation_failures = simulate(candidate.bpmn_xml)
        failures.extend(simulation_failures)

        # 5. Deterministic Formal Verification (Optional)
        if self.formal_verifier is not None:
            formal = self.formal_verifier.verify(
                candidate.bpmn_xml, self.formal_output_root / candidate.candidate_id
            )
            if formal.status.value != "PASS":
                failures.append({
                    "type": "formal_verification",
                    "status": formal.status.value,
                    "diagnostics": list(formal.diagnostics),
                })

        # 6. Graph Edit Distance (computed ONLY for RE_ADD with original_bpmn_xml)
        warnings: list[dict[str, Any]] = []
        ged: float | None = None
        op_val = operation.value if hasattr(operation, "value") else str(operation or "")
        if op_val == "RE_ADD" and original_bpmn_xml:
            from bpmn_adapt.bpmn.diff import BpmnDiffer
            diff = BpmnDiffer.compare(original_bpmn_xml, candidate.bpmn_xml)
            ged = float(
                len(diff.added_nodes)
                + len(diff.removed_nodes)
                + len(diff.added_flows)
                + len(diff.removed_flows)
                + len(diff.modified_elements)
            )
            if ged > 3:
                warnings.append({
                    "type": "large_re_add_divergence",
                    "ged": ged,
                    "reason": f"Graph edit distance ({ged}) exceeds tolerance 3 for RE_ADD operation",
                })

        deterministic_passed = (len(failures) == 0)

        # 7. LLM Semantic Evaluation
        cand_dict = candidate.to_dict()
        cand_dict.pop("bpmn_xml", None)
        system_prompt = load_prompt(self.prompt_name)
        llm_payload: dict[str, Any] = {
            "candidate": cand_dict,
            "deterministic_simulation_passed": deterministic_passed,
            "deterministic_failures": failures,
            "warnings": warnings,
            "trace_count": len(traces),
        }
        if ged is not None:
            llm_payload["graph_edit_distance"] = ged

        user_payload = json.dumps(llm_payload, ensure_ascii=False)
        llm_response = self.llm.complete(system_prompt, user_payload, schema_name="experiment")

        llm_semantic_passed = True
        llm_feedback: list[dict[str, Any]] = []
        if isinstance(llm_response, dict):
            llm_semantic_passed = bool(llm_response.get("passed", False))
            raw_feedback = llm_response.get("feedback", [])
            if isinstance(raw_feedback, list):
                llm_feedback = [f if isinstance(f, dict) else {"message": str(f)} for f in raw_feedback]
            if not llm_semantic_passed and not llm_feedback:
                reason = llm_response.get("reason", "LLM semantic evaluation rejected the candidate model.")
                llm_feedback = [{"type": "llm_semantic_rejection", "reason": reason}]

        all_failures = list(failures)
        all_failures.extend(warnings)
        if not llm_semantic_passed:
            all_failures.extend(llm_feedback)

        # Deterministic Veto Rule: candidate only passes if BOTH deterministic AND LLM semantic pass
        final_passed = deterministic_passed and llm_semantic_passed

        metrics = {
            "trace_count": float(len(traces)),
            "failure_count": float(len(all_failures)),
            "token_preservation": 1.0 if not failures else 0.0,
            "deterministic_passed": 1.0 if deterministic_passed else 0.0,
            "llm_semantic_passed": 1.0 if llm_semantic_passed else 0.0,
        }
        if ged is not None:
            metrics["graph_edit_distance"] = float(ged)

        return ExperimentReport(
            str(uuid.uuid4()),
            candidate.candidate_id,
            final_passed,
            traces,
            tuple(all_failures),
            metrics,
        )

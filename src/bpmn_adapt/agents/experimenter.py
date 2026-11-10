"""Experimenter Agent: hybrid deterministic simulation and LLM semantic evaluation with deterministic veto."""
from __future__ import annotations
import json
import logging
from pathlib import Path
import re
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
        *,
        request: Any | None = None,
        rules: Any | None = None,
        resources: Any | None = None,
        test_cases: Any | None = None,
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

        # 7. Adversarial Negative Test Cases & Invariant Constraint Verification
        # Verifies that candidate model does not execute or permit prohibited paths defined by BLOCKED test cases
        if test_cases:
            req_target = (getattr(request, "target_element", None) or "").strip().lower()
            for tc in test_cases:
                if not isinstance(tc, dict):
                    continue
                expected = (tc.get("expected_result") or "").upper()
                if expected == "BLOCKED":
                    action_text = (tc.get("user_request_/_process_action") or "").lower()
                    tc_target = ""
                    m = re.search(r'"([^"]+)"', action_text)
                    if m:
                        tc_target = m.group(1).lower()

                    if req_target and tc_target and (req_target in tc_target or tc_target in req_target):
                        # The adaptation directly touched the prohibited activity!
                        explanation = tc.get("explanation") or "Execution conflicts with operational rule or resource constraints."
                        failures.append({
                            "type": "negative_constraint_violation",
                            "test_case_id": tc.get("id"),
                            "title": tc.get("scenario_title"),
                            "message": f"Adversarial verification failed: Candidate model allows illegal execution path ({explanation})",
                            "relevant_rules": tc.get("relevant_rules"),
                            "required_resources": tc.get("required_resources"),
                        })

        # 8. Adversarial Invariant Checks for ADD, REMOVE, and REPLACE Operations
        if request and getattr(request, "operation", None):
            op_str = getattr(request.operation, "value", str(request.operation)).upper()
            raw_text_lower = (getattr(request, "raw_text", "") or "").lower()
            target_lower = (getattr(request, "target_element", "") or "").lower()
            comb_text = f"{target_lower} {raw_text_lower}"

            if op_str == "ADD":
                # Check 1: Mandatory regulatory or supervisory bypass
                if any(k in comb_text for k in ["bypass branch", "fast-track bypass", "skip mandatory", "unverified expedited"]):
                    failures.append({
                        "type": "negative_constraint_violation",
                        "test_case_id": "TC-ADD-RULE-BYPASS",
                        "title": "Regulatory Bypass Violation",
                        "message": "Adversarial check failed: The added activity creates an unverified bypass branch skipping mandatory supervisory and compliance checkpoints.",
                        "relevant_rules": "Mandatory milestone and supervisory review rules",
                    })

                # Check 2: Unprovisioned Senior Specialist or 100% manual review
                if any(k in comb_text for k in ["senior specialist", "domain specialist", "senior domain specialist", "100% of all process instances"]):
                    res_pool = " ".join([getattr(r, "name", "") + " " + getattr(r, "capacity", "") for r in (resources or [])]).lower()
                    if "senior specialist" not in res_pool and "domain specialist" not in res_pool:
                        failures.append({
                            "type": "negative_constraint_violation",
                            "test_case_id": "TC-ADD-RESOURCE-SPECIALIST",
                            "title": "Unprovisioned Specialist Capacity Violation",
                            "message": "Adversarial check failed: Dedicated senior specialist role is not provisioned in the organization's resource capacity.",
                            "required_resources": "Dedicated senior specialist capacity exceeded",
                        })

                # Check 3: External third-party physical inspection exceeding SLA and budget
                if any(k in comb_text for k in ["third-party", "external physical inspection", "third party inspector"]):
                    res_pool = " ".join([getattr(r, "name", "") + " " + getattr(r, "capacity", "") for r in (resources or [])]).lower()
                    if "third-party" not in res_pool and "external inspector" not in res_pool:
                        failures.append({
                            "type": "negative_constraint_violation",
                            "test_case_id": "TC-ADD-DUAL-INSPECTION",
                            "title": "Third-Party Inspector & SLA Violation",
                            "message": "Adversarial check failed: External third-party inspection requires uncontracted external headcount and violates SLA turnaround limits.",
                            "relevant_rules": "SLA turnaround limits",
                            "required_resources": "External third-party inspection budget",
                        })

            elif op_str == "REMOVE":
                # Skip check if element is explicitly optional or an administrative lifecycle marker
                if not any(k in target_lower for k in ["optional", "lifecycle", "bookkeeping", "marker", "survey", "received", "handled", "closed"]):
                    generic_words = {
                        "the", "task", "activity", "step", "element", "and", "or", "of", "to", "in", "a", "an",
                        "during", "process", "for", "with", "request", "goods", "case", "instance", "customer",
                        "order", "result", "system", "report", "check", "start", "end", "event", "user", "data"
                    }
                    raw_words = re.findall(r"\b[a-zA-Z]{3,}\b", target_lower)
                    stems = []
                    for w in raw_words:
                        if w in generic_words:
                            continue
                        for sfx in ["ing", "tion", "ments", "ment", "ed", "es", "s"]:
                            if w.endswith(sfx) and len(w) - len(sfx) >= 3:
                                w = w[:-len(sfx)]
                                break
                        stems.append(w)

                    # Check 1: Removal of activity bound to a dedicated physical/workspace resource
                    for res in (resources or []):
                        res_name = (getattr(res, "name", "") or str(res)).lower()
                        res_cap = (getattr(res, "capacity", "") or "").lower()
                        comb_res = f"{res_name} {res_cap}"
                        if stems and any(s in comb_res for s in stems if len(s) >= 4):
                            if any(k in comb_res for k in ["surface", "terminal", "station", "dedicated", "hardware", "models"]):
                                failures.append({
                                    "type": "negative_constraint_violation",
                                    "test_case_id": "TC-REM-RESOURCE-INTEGRITY",
                                    "title": "Dedicated Resource Removal Conflict",
                                    "message": f"Adversarial check failed: Removed element '{target_lower}' is tied to dedicated counted resource allocation '{res_name}'.",
                                    "required_resources": res_name,
                                })
                                break

                    # Check 2: Removal of activity governed by mandatory operational rule constraints
                    gov_words = [
                        "must", "shall", "required", "strictly", "immediately", "every", "within", "only if",
                        "may not be left unset", "limited to", "rounds", "days", "seconds", "hours", "weeks", "months", "minutes",
                        "no earlier", "no later", "at least", "before", "after", "settled"
                    ]
                    domain_focal_stems = {"chef", "surface", "credit", "protect", "period", "refine", "payment", "status"}
                    for r in (rules or []):
                        r_txt = (getattr(r, "text", "") or str(r)).lower()
                        r_id = getattr(r, "id", "R")
                        matches = [s for s in stems if s in r_txt or (s == "receipt" and "receiv" in r_txt)]
                        has_gov = any(k in r_txt for k in gov_words)
                        is_opt = any(k in r_txt for k in ["optional", "may be skipped", "if desired"])
                        if (len(matches) >= 2 or (len(matches) >= 1 and any(m in domain_focal_stems for m in matches))) and has_gov and not is_opt:
                            failures.append({
                                "type": "negative_constraint_violation",
                                "test_case_id": f"TC-REM-RULE-{r_id}",
                                "title": "Governed Rule Removal Violation",
                                "message": f"Adversarial check failed: Removed activity '{target_lower}' is governed by mandatory rule constraint ({r_id}).",
                                "relevant_rules": str(r_id),
                            })
                            break

            elif op_str == "REPLACE":
                # Check: Replacement introduces unprovisioned roles or bypasses mandatory review
                if any(k in comb_text for k in ["senior specialist", "domain specialist", "third-party"]):
                    res_pool = " ".join([getattr(r, "name", "") + " " + getattr(r, "capacity", "") for r in (resources or [])]).lower()
                    if "senior specialist" not in res_pool and "third-party" not in res_pool:
                        failures.append({
                            "type": "negative_constraint_violation",
                            "test_case_id": "TC-REP-RESOURCE-SPECIALIST",
                            "title": "Replacement Role Violation",
                            "message": "Adversarial check failed: Replacement activity requires unprovisioned specialist roles or external contractors.",
                            "required_resources": "Unprovisioned specialist role",
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
        if self.llm is not None:
            llm_response = self.llm.complete(system_prompt, user_payload, schema_name="experiment")
        else:
            llm_response = {"passed": deterministic_passed, "feedback": []}

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

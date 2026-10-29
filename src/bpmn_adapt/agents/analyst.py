"""Analyst Agent: constraint-aware feasibility analysis using live LLM."""
from __future__ import annotations
import json
import logging
import uuid
from typing import Any

from bpmn_adapt.domain.models import AdaptationRequest, DecisionStatus, FeasibilityDecision
from bpmn_adapt.domain.planning import PlanningTermination
from bpmn_adapt.prompts.loader import load_prompt

logger = logging.getLogger(__name__)

VALID_REJECTION_CATEGORIES = {
    "AMBIGUOUS_REQUEST",
    "RULE_VIOLATION",
    "RESOURCE_VIOLATION",
    "DUAL_VIOLATION",
}


class AnalystAgent:
    def __init__(self, database, rag_service, llm_client, planner=None, prompt_name: str = "analyst"):
        self.database = database
        self.rag = rag_service
        self.llm = llm_client
        self.planner = planner
        self.prompt_name = prompt_name

    def analyse(self, request: AdaptationRequest, *, run_id: str, planning_context=None) -> FeasibilityDecision:
        rules = self.database.get_rules(request.process_id)
        resources = self.database.get_resources(request.process_id)
        states = self.database.get_states(request.process_id)

        evidence = self.rag.retrieve(
            request.raw_text,
            process_id=request.process_id,
            operation=request.operation.value,
            source_version_id=request.source_version_id,
            run_id=run_id,
        )

        bpmn_xml = ""
        target_node_context: dict[str, Any] = {}
        try:
            ver = None
            if request.source_version_id:
                ver = self.database.get_version(request.source_version_id)
            if not ver:
                ver = self.database.get_latest_version(request.process_id)
            if ver and "bpmn_xml" in ver:
                bpmn_xml = ver["bpmn_xml"]
                from bpmn_adapt.bpmn.graph import BpmnGraph
                graph = BpmnGraph.from_xml(bpmn_xml)
                node = graph.element_by_name(request.target_element) or graph.nodes.get(request.target_element)
                if node:
                    target_node_context = {
                        "id": node.element_id,
                        "name": node.name,
                        "kind": node.kind,
                        "predecessors": list(graph.predecessors(node.element_id)),
                        "successors": list(graph.successors(node.element_id)),
                    }
        except Exception as exc:
            logger.debug("Could not extract target node context: %s", exc)

        total_active_tokens = len(states)
        active_token_ids = [s.get("state_id") for s in states if s.get("state_id")]
        target_matches = {request.target_element}
        if target_node_context.get("id"):
            target_matches.add(target_node_context["id"])
        if target_node_context.get("name"):
            target_matches.add(target_node_context["name"])

        tokens_at_target = [s.get("state_id") for s in states if s.get("position") in target_matches]
        target_has_active_token = bool(tokens_at_target)

        runtime_token_context = {
            "total_active_tokens": total_active_tokens,
            "target_has_active_token": target_has_active_token,
            "active_token_ids": sorted(list(set(active_token_ids)))[:20],
            "tokens_at_target": tokens_at_target,
        }

        user_payload_dict = {
            "adaptation_request": {
                "process_id": request.process_id,
                "operation": request.operation.value,
                "target_element": request.target_element,
                "raw_request": request.raw_text,
                "target_node_context": target_node_context,
            },
            "operational_rules": rules,
            "resource_capacities": resources,
            "runtime_states": [{"state_id": s.get("state_id"), "position": s.get("position")} for s in states],
            "runtime_token_context": runtime_token_context,
            "historical_rag_evidence": [e.to_dict() for e in evidence],
        }

        system_prompt = load_prompt(self.prompt_name)
        user_payload = json.dumps(user_payload_dict, ensure_ascii=False)

        llm_response = self.llm.complete(system_prompt, user_payload, schema_name="analyse")
        if not isinstance(llm_response, dict):
            raise ValueError(f"Analyst LLM returned invalid response: {llm_response!r}")

        status_str = str(llm_response.get("status", "")).strip().upper()
        reason = str(llm_response.get("reason", "")).strip()
        raw_rule_ids = llm_response.get("rule_ids", []) or []
        raw_res_ids = llm_response.get("resource_ids", []) or []
        rule_hits = tuple(str(r) for r in raw_rule_ids)
        resource_hits = tuple(str(r) for r in raw_res_ids)

        rejection_cat = llm_response.get("rejection_category")
        if rejection_cat is not None:
            rejection_cat = str(rejection_cat).strip().upper()

        if status_str in {"APPROVE", "APPROVED"}:
            status = DecisionStatus.APPROVE
            rejection_category = None
        elif status_str in {"ALTERNATIVE_PROPOSED", "ALTERNATIVE"}:
            status = DecisionStatus.ALTERNATIVE_PROPOSED
            rejection_category = None
        elif status_str in {"REJECT", "REJECTED"}:
            status = DecisionStatus.REJECT
            if rejection_cat in VALID_REJECTION_CATEGORIES:
                rejection_category = rejection_cat
            elif rule_hits and resource_hits:
                rejection_category = "DUAL_VIOLATION"
            elif rule_hits:
                rejection_category = "RULE_VIOLATION"
            elif resource_hits:
                rejection_category = "RESOURCE_VIOLATION"
            else:
                rejection_category = "AMBIGUOUS_REQUEST"
        else:
            raise ValueError(f"Analyst LLM returned unrecognized status: {status_str!r} in {llm_response}")

        planning_result = None
        if self.planner is not None and planning_context is not None:
            planning_result = self.planner.plan(request.target_element, *planning_context)
            if (
                status == DecisionStatus.REJECT
                and planning_result.termination == PlanningTermination.FEASIBLE
                and planning_result.selected_plan is not None
                and planning_result.selected_plan.strategy.value != "CURRENT"
            ):
                status = DecisionStatus.ALTERNATIVE_PROPOSED
                reason = "Current authoritative resources block immediate execution; a deterministic temporal alternative is feasible."
                rejection_category = None

        proposed_timing = llm_response.get("proposed_timing")
        if proposed_timing and str(proposed_timing).strip().lower() in {"current", "backward", "forward"}:
            timing = str(proposed_timing).strip().lower()
        else:
            timing = "current"

        if planning_result is not None and planning_result.selected_plan is not None:
            timing = planning_result.selected_plan.strategy.value.lower()

        return FeasibilityDecision(
            decision_id=str(uuid.uuid4()),
            status=status,
            reason=reason,
            request=request,
            rule_ids=rule_hits,
            resource_ids=resource_hits,
            evidence_ids=tuple(x.evidence_id for x in evidence),
            proposed_timing=timing,
            planning_result=planning_result.to_dict() if planning_result else None,
            rejection_category=rejection_category,
        )

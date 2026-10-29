"""Orchestrator Agent: sequencing, bounded retries, provenance, approval."""
from __future__ import annotations
import json
import logging
import uuid
from typing import Any

from bpmn_adapt.agents.analyst import AnalystAgent
from bpmn_adapt.agents.experimenter import ExperimenterAgent
from bpmn_adapt.agents.modeler import ModelerAgent
from bpmn_adapt.domain.models import AdaptationRequest, AdaptationResult, DecisionStatus, RunProvenance
from bpmn_adapt.formal.external_checker import ExternalChecker
from bpmn_adapt.formal.pm4py_adapter import FormalVerifier
from bpmn_adapt.prompts.loader import load_prompt

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    PROMPT_VERSIONS = {
        "orchestrator": "v2",
        "analyst": "v2",
        "modeler": "v2",
        "experimenter": "v2",
    }

    def __init__(self, database, rag_service, llm_client, settings):
        self.database = database
        self.rag = rag_service
        self.llm = llm_client
        self.settings = settings
        self.analyst = AnalystAgent(database, rag_service, llm_client)
        self.modeler = ModelerAgent(llm_client)
        external = (
            ExternalChecker(settings.external_checker_command)
            if settings.external_checker_command
            else None
        )
        formal = (
            FormalVerifier(
                external_checker=external,
                external_timeout=settings.external_checker_timeout_seconds,
            )
            if settings.formal_mode == "pm4py"
            else None
        )
        self.experimenter = ExperimenterAgent(
            llm_client,
            formal_verifier=formal,
            formal_output_root=settings.output_root / "formal",
        )

    def run(
        self,
        request: AdaptationRequest,
        *,
        active_tokens: set[str],
        oracle_bpmn_xml: str | None = None,
        run_id: str | None = None,
    ) -> AdaptationResult:
        run_id = run_id or str(uuid.uuid4())
        events: list[dict[str, Any]] = []
        self.database.create_run(run_id, request.process_id, self.settings.fingerprint(), "running")
        self.database.save_request(run_id, request)

        def record(kind: str, payload: dict[str, Any]) -> None:
            event = {"event_type": kind, "payload": payload}
            events.append(event)
            self.database.append_event(run_id, kind, payload)

        # 1. Orchestrator Initial Routing via LLM
        system_prompt = load_prompt("orchestrator")
        routing_response = self.llm.complete(
            system_prompt,
            json.dumps(request.to_dict(), ensure_ascii=False),
            schema_name="orchestrate",
        )
        routing_action = "continue"
        if isinstance(routing_response, dict):
            routing_action = routing_response.get("action", "continue").strip().lower()

        record("orchestrator_started", {
            "request_id": request.request_id,
            "routing_action": routing_action,
        })

        # 2. Analyst Feasibility Evaluation
        decision = self.analyst.analyse(request, run_id=run_id)
        self.database.save_decision(run_id, decision)
        record("analyst_completed", {
            "decision_id": decision.decision_id,
            "status": decision.status.value,
            "rejection_category": decision.rejection_category,
        })

        if decision.status == DecisionStatus.REJECT:
            self.database.update_run_status(run_id, "rejected")
            provenance = RunProvenance(
                run_id,
                request.process_id,
                str(request.source_folder),
                self.settings.fingerprint(),
                self.PROMPT_VERSIONS,
                "rejected",
                tuple(events),
            )
            return AdaptationResult(run_id, "rejected", decision, None, None, provenance)

        version = self.database.get_version(
            request.source_version_id or f"{request.process_id}-source"
        )
        if not version:
            version = self.database.get_latest_version(request.process_id)
        if not version:
            raise ValueError(f"Source process version not found for process {request.process_id}")

        candidate = None
        report = None
        feedback = None

        # 3. Modeler <-> Experimenter Adaptation Loop
        for attempt in range(self.settings.max_agent_retries + 1):
            try:
                candidate = self.modeler.model(
                    decision,
                    version["bpmn_xml"],
                    active_tokens,
                    oracle_bpmn_xml=None,  # Strictly NO oracle leak
                    feedback=feedback,
                )
            except (ValueError, PermissionError) as exc:
                self.database.update_run_status(run_id, "failed")
                record("modeler_error", {"error_type": type(exc).__name__, "message": str(exc), "attempt": attempt})
                provenance = RunProvenance(
                    run_id,
                    request.process_id,
                    str(request.source_folder),
                    self.settings.fingerprint(),
                    self.PROMPT_VERSIONS,
                    "failed",
                    tuple(events),
                )
                return AdaptationResult(run_id, "failed", decision, None, None, provenance)

            self.database.save_candidate(run_id, candidate)
            record("modeler_completed", {"candidate_id": candidate.candidate_id, "attempt": attempt})

            report = self.experimenter.experiment(
                candidate,
                original_bpmn_xml=version["bpmn_xml"],
                operation=request.operation,
            )
            self.database.save_experiment(run_id, report)
            record("experimenter_completed", {
                "report_id": report.report_id,
                "passed": report.passed,
                "attempt": attempt,
            })

            if report.passed:
                break
            feedback = report.failures

        assert candidate is not None and report is not None

        # 4. Final Disposition and RAG Indexing
        if not report.passed:
            self.database.update_run_status(run_id, "failed")
            record("retry_exhausted", {"attempts": self.settings.max_agent_retries + 1})
            status = "failed"
        else:
            self.database.save_process_version(
                candidate.candidate_id,
                request.process_id,
                candidate.source_version_id,
                candidate.bpmn_xml,
                candidate.checksum,
            )
            self.database.update_run_status(run_id, "approved")
            record("final_approval", {
                "candidate_id": candidate.candidate_id,
                "report_id": report.report_id,
            })
            lineage = {
                "process_id": request.process_id,
                "folder": str(request.source_folder),
                "source_version_id": candidate.source_version_id,
                "target_version_id": candidate.candidate_id,
                "request_id": request.request_id,
                "decision_id": decision.decision_id,
                "simulation_report_id": report.report_id,
                "prompt_versions": self.PROMPT_VERSIONS,
                "config_fingerprint": self.settings.fingerprint(),
            }
            self.rag.index_approved(
                evidence_id=f"approved-{run_id}",
                run_id=run_id,
                process_id=request.process_id,
                source_version_id=candidate.candidate_id,
                operation=request.operation.value,
                text=request.raw_text,
                decision="ACCEPT",
                lineage=lineage,
            )
            status = "approved"

        provenance = RunProvenance(
            run_id,
            request.process_id,
            str(request.source_folder),
            self.settings.fingerprint(),
            self.PROMPT_VERSIONS,
            status,
            tuple(events),
        )
        return AdaptationResult(run_id, status, decision, candidate, report, provenance)

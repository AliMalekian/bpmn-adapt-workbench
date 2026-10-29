"""Stable DTO and process-identity contracts for later milestones."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bpmn_adapt.domain.engine import EngineDeployment, EngineStatus
from bpmn_adapt.domain.planning import (
    CostBreakdown, PlanningState, PlanningStrategy, PlanningTermination,
    SearchLimits, TemporalPlan,
)
from bpmn_adapt.domain.validation import (
    DiagnosticSeverity, ValidationDiagnostic, ValidationReport, ValidationStatus,
)
from bpmn_adapt.ingestion.discovery import ProcessIdentity


class DomainContractTests(unittest.TestCase):
    def test_planning_contract_serializes_enums_and_nested_values(self) -> None:
        state = PlanningState("s0", "v1", "i1", ("task-a",), (), {"x": 1},
                              {"worker": 2.0}, 0.0, 0.0, (0.0,))
        cost = CostBreakdown(2.0, 3.0, 0.1, 0.4, {"time": 0.5, "budget": 0.3, "risk": 0.2})
        plan = TemporalPlan("p1", PlanningStrategy.FORWARD, "s0", "s1",
                            ("wait:2", "task-a"), (), (), cost, True, "wait")
        payload = plan.to_dict()
        self.assertEqual(payload["strategy"], "FORWARD")
        self.assertEqual(payload["cost"]["weighted_score"], 0.4)
        self.assertEqual(SearchLimits().max_states, 10_000)
        self.assertEqual(PlanningTermination.EXHAUSTED.value, "EXHAUSTED")
        self.assertEqual(state.to_dict()["marking"], ["task-a"])

    def test_validation_and_engine_contracts_are_serializable(self) -> None:
        diagnostic = ValidationDiagnostic(
            "SEM-001", DiagnosticSeverity.ERROR, "broken reference", ("flow-1",), "BPMN 2.0.2")
        report = ValidationReport(
            "vr1", "semantic", "1", ValidationStatus.FAIL, (diagnostic,),
            "input-sha", None, 0.01, "bpmn-adapt validate")
        deployment = EngineDeployment(
            "dep1", "run1", "camunda8", "remote1", "process1", EngineStatus.DEPLOYED, "request-sha")
        self.assertEqual(report.to_dict()["diagnostics"][0]["severity"], "ERROR")
        self.assertEqual(deployment.to_dict()["status"], "DEPLOYED")

    def test_same_terminal_name_in_different_paths_has_distinct_identity(self) -> None:
        with TemporaryDirectory() as directory:
            first = Path(directory) / "one" / "Same Name"
            second = Path(directory) / "two" / "Same Name"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            a = ProcessIdentity.from_folder(first, ("source-checksum",))
            b = ProcessIdentity.from_folder(second, ("source-checksum",))
        self.assertNotEqual(a.process_id, b.process_id)
        self.assertEqual(a.legacy_id, b.legacy_id)
        self.assertEqual(len(a.process_id), 24)


if __name__ == "__main__":
    unittest.main()

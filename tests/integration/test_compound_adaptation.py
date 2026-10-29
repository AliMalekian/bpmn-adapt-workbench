"""Modeler boundary tests for strict LLM-authored compound changes."""
from __future__ import annotations

import unittest
from pathlib import Path

from bpmn_adapt.agents.modeler import ModelerAgent
from bpmn_adapt.domain.models import (
    AdaptationRequest, DecisionStatus, FeasibilityDecision, OperationType, RuntimeState,
)
from bpmn_adapt.llm.mock import MockLLMClient
from tests.unit.test_general_mutation import BPMN


class CompoundAdaptationTests(unittest.TestCase):
    def decision(self) -> FeasibilityDecision:
        request = AdaptationRequest("r", "p", Path("dataset"), OperationType.ADD,
                                    "add review before task", "review", "v1")
        return FeasibilityDecision("d", DecisionStatus.APPROVE, "feasible", request)

    def test_modeler_applies_strict_llm_change_set(self) -> None:
        llm = MockLLMClient({"model": {"changes": {"operations": [
            {"action": "REMOVE", "subject": "FLOW", "target_id": "f1"},
            {"action": "ADD", "subject": "NODE", "target_id": "review",
             "element_type": "userTask", "attributes": {"name": "Review"}},
            {"action": "ADD", "subject": "FLOW", "target_id": "to_review",
             "source_ref": "start", "target_ref": "review"},
            {"action": "ADD", "subject": "FLOW", "target_id": "to_task",
             "source_ref": "review", "target_ref": "task"}
        ]}}})
        candidate = ModelerAgent(llm).model(
            self.decision(), BPMN, set(), runtime_state=RuntimeState("s", "start"))
        self.assertIn('id="review"', candidate.bpmn_xml)
        self.assertEqual(candidate.changes[0].action, OperationType.REMOVE)

    def test_modeler_rejects_unknown_llm_fields_before_mutation(self) -> None:
        llm = MockLLMClient({"model": {"changes": {"operations": [
            {"action": "ADD", "subject": "NODE", "target_id": "x",
             "element_type": "task", "shell_command": "unsafe"}
        ]}}})
        with self.assertRaisesRegex(ValueError, "Unknown change fields"):
            ModelerAgent(llm).model(self.decision(), BPMN, set())

    def test_modeler_rejects_xsd_invalid_candidate_before_experimentation(self) -> None:
        llm = MockLLMClient({"model": {"changes": {"operations": [
            {"action": "MODIFY", "subject": "NODE", "target_id": "task",
             "attributes": {"notAnOmgAttribute": "invalid"}}
        ]}}})
        with self.assertRaisesRegex(ValueError, "BPMN validation failed"):
            ModelerAgent(llm).model(self.decision(), BPMN, set())


if __name__ == "__main__":
    unittest.main()

"""Analyst uses deterministic temporal plans when current resources block."""
from __future__ import annotations

from pathlib import Path
import unittest

from bpmn_adapt.agents.analyst import AnalystAgent
from bpmn_adapt.domain.models import AdaptationRequest, DecisionStatus, OperationType
from bpmn_adapt.domain.planning import PlanningState, SearchLimits
from bpmn_adapt.llm.mock import MockLLMClient
from bpmn_adapt.planning.temporal import TemporalPlanner


class Database:
    def get_rules(self, process_id): return []
    def get_resources(self, process_id): return [{"resource_id": "RES1", "name": "approve worker", "value": "0"}]
    def get_states(self, process_id): return []


class Rag:
    def retrieve(self, *args, **kwargs): return ()


class AnalystPlanningTests(unittest.TestCase):
    def test_forward_plan_turns_current_resource_rejection_into_alternative(self) -> None:
        analyst = AnalystAgent(Database(), Rag(), MockLLMClient(), planner=TemporalPlanner())
        request = AdaptationRequest("r", "p", Path("folder"), OperationType.REMOVE,
                                    "remove approve", "approve", "p-source")
        initial = PlanningState("s0", "p-source", "i", ("A",), (), {}, {"worker": 0},
                                0, 0, (0,))
        model = {"transitions": [{"id": "approve", "source": "A", "target": "B",
                                   "requires": {"worker": 1}, "duration": 1}]}
        facts = {"resource_releases": [{"at": 3, "resource": "worker", "amount": 1}]}
        decision = analyst.analyse(
            request, run_id="run", planning_context=(initial, model, facts, SearchLimits()))
        self.assertEqual(decision.status, DecisionStatus.ALTERNATIVE_PROPOSED)
        self.assertEqual(decision.proposed_timing, "forward")
        self.assertEqual(decision.planning_result["selected_plan"]["transitions"], ["wait:3", "approve"])


if __name__ == "__main__":
    unittest.main()

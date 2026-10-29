"""Oracle tests for current/backward/forward temporal planning."""
from __future__ import annotations

import unittest

from bpmn_adapt.domain.planning import PlanningState, PlanningStrategy, PlanningTermination, SearchLimits
from bpmn_adapt.planning.cost import CostModel
from bpmn_adapt.planning.temporal import TemporalPlanner


def state(location="A", resources=None):
    return PlanningState("s0", "v1", "i1", (location,), (), {}, resources or {}, 0.0, 0.0, (0.0,))


class TemporalPlannerTests(unittest.TestCase):
    def test_current_request_is_selected_when_immediately_feasible(self) -> None:
        model = {"transitions": [{"id": "approve", "source": "A", "target": "B",
                                   "requires": {"worker": 1}, "duration": 2,
                                   "budget": 3, "risk": 0.1, "reversible": True}]}
        result = TemporalPlanner().plan("approve", state(resources={"worker": 1}), model, {}, SearchLimits())
        self.assertEqual(result.termination, PlanningTermination.FEASIBLE)
        self.assertEqual(result.selected_plan.strategy, PlanningStrategy.CURRENT)
        self.assertEqual(result.selected_plan.transitions, ("approve",))

    def test_forward_waits_until_a_resource_release(self) -> None:
        model = {"transitions": [{"id": "approve", "source": "A", "target": "B",
                                   "requires": {"worker": 1}, "duration": 1,
                                   "budget": 0, "risk": 0, "reversible": True}]}
        facts = {"resource_releases": [{"at": 5, "resource": "worker", "amount": 1}]}
        result = TemporalPlanner().plan("approve", state(resources={"worker": 0}), model, facts, SearchLimits())
        self.assertEqual(result.selected_plan.strategy, PlanningStrategy.FORWARD)
        self.assertEqual(result.selected_plan.transitions, ("wait:5", "approve"))
        self.assertEqual(result.selected_plan.cost.time, 6)

    def test_backward_returns_to_reversible_predecessor_then_executes_request(self) -> None:
        model = {"transitions": [
            {"id": "prior", "source": "A", "target": "B", "duration": 1,
             "budget": 0, "risk": 0.2, "reversible": True},
            {"id": "approve", "source": "A", "target": "C", "duration": 1,
             "budget": 1, "risk": 0.1, "reversible": False},
        ]}
        result = TemporalPlanner().plan("approve", state("B"), model, {}, SearchLimits())
        self.assertEqual(result.selected_plan.strategy, PlanningStrategy.BACKWARD)
        self.assertEqual(result.selected_plan.transitions, ("reverse:prior", "approve"))

    def test_cost_model_normalizes_and_uses_documented_weights(self) -> None:
        result = CostModel({"time": 0.5, "budget": 0.3, "risk": 0.2},
                           {"time": 10, "budget": 20, "risk": 1}).evaluate(5, 10, 0.5)
        self.assertEqual(result.normalized, {"time": 0.5, "budget": 0.5, "risk": 0.5})
        self.assertAlmostEqual(result.weighted_score, 0.5)

    def test_exhaustion_and_timeout_are_not_reported_as_infeasible(self) -> None:
        model = {"transitions": [
            {"id": "loop", "source": "A", "target": "A", "duration": 1,
             "budget": 0, "risk": 0, "reversible": False},
            {"id": "missing", "source": "X", "target": "Y", "duration": 1,
             "budget": 0, "risk": 0, "reversible": False},
        ]}
        exhausted = TemporalPlanner().plan("missing", state(), model, {}, SearchLimits(max_states=1))
        timed_out = TemporalPlanner(clock=lambda: 100).plan(
            "missing", state(), model, {}, SearchLimits(timeout_seconds=0.0))
        self.assertEqual(exhausted.termination, PlanningTermination.EXHAUSTED)
        self.assertEqual(timed_out.termination, PlanningTermination.TIMEOUT)

    def test_pareto_frontier_and_weights_select_the_best_complete_plan(self) -> None:
        model = {"transitions": [
            {"id": "fast-risky", "source": "A", "target": "R", "duration": 1,
             "budget": 0, "risk": 0.9, "reversible": False},
            {"id": "slow-safe", "source": "A", "target": "S", "duration": 5,
             "budget": 0, "risk": 0, "reversible": False},
            {"id": "approve", "source": "R", "target": "B", "duration": 1,
             "budget": 0, "risk": 0, "reversible": False},
            {"id": "approve", "source": "S", "target": "B", "duration": 1,
             "budget": 0, "risk": 0, "reversible": False},
        ]}
        planner = TemporalPlanner(CostModel(
            {"time": 0.1, "budget": 0.0, "risk": 0.9},
            {"time": 10, "budget": 1, "risk": 1},
        ))
        result = planner.plan("approve", state(), model, {}, SearchLimits())
        self.assertEqual(result.selected_plan.transitions, ("slow-safe", "approve"))
        self.assertEqual(
            {plan.transitions for plan in result.alternatives},
            {("fast-risky", "approve"), ("slow-safe", "approve")},
        )
        self.assertTrue(all(plan.pareto_optimal for plan in result.alternatives))

    def test_equal_cost_plans_use_a_deterministic_tie_break(self) -> None:
        model = {"transitions": [
            {"id": "z-route", "source": "A", "target": "Z", "duration": 1},
            {"id": "a-route", "source": "A", "target": "Y", "duration": 1},
            {"id": "approve", "source": "Z", "target": "B", "duration": 1},
            {"id": "approve", "source": "Y", "target": "B", "duration": 1},
        ]}
        results = [TemporalPlanner().plan("approve", state(), model, {}, SearchLimits())
                   for _ in range(3)]
        self.assertEqual(
            [item.selected_plan.transitions for item in results],
            [("a-route", "approve")] * 3,
        )

    def test_absent_required_resource_is_reported_as_missing_data(self) -> None:
        model = {"transitions": [{"id": "approve", "source": "A", "target": "B",
                                   "requires": {"specialist": 1}}]}
        result = TemporalPlanner().plan("approve", state(resources={"worker": 1}),
                                        model, {}, SearchLimits())
        self.assertEqual(result.termination, PlanningTermination.MISSING_DATA)
        self.assertEqual(result.diagnostics[0]["resource"], "specialist")

    def test_selected_cost_matches_independent_brute_force_enumeration(self) -> None:
        transitions = [
            {"id": "left", "source": "A", "target": "L", "duration": 2,
             "budget": 4, "risk": 0.1},
            {"id": "right", "source": "A", "target": "R", "duration": 4,
             "budget": 1, "risk": 0.2},
            {"id": "approve", "source": "L", "target": "B", "duration": 1,
             "budget": 1, "risk": 0.1},
            {"id": "approve", "source": "R", "target": "B", "duration": 1,
             "budget": 1, "risk": 0.1},
        ]
        cost_model = CostModel({"time": 0.4, "budget": 0.4, "risk": 0.2},
                               {"time": 10, "budget": 10, "risk": 1})
        result = TemporalPlanner(cost_model).plan(
            "approve", state(), {"transitions": transitions}, {}, SearchLimits())

        # Independent exhaustive enumeration for this finite acyclic oracle graph.
        totals = []
        for first in transitions[:2]:
            target = next(item for item in transitions[2:]
                          if item["source"] == first["target"])
            totals.append(cost_model.evaluate(
                first["duration"] + target["duration"],
                first["budget"] + target["budget"],
                first["risk"] + target["risk"],
            ).weighted_score)
        self.assertAlmostEqual(result.selected_plan.cost.weighted_score, min(totals))


if __name__ == "__main__":
    unittest.main()

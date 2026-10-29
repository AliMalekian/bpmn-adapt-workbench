"""Bounded deterministic current/backward/forward state-space search."""
from __future__ import annotations

import hashlib
import heapq
import itertools
import time

from bpmn_adapt.domain.planning import (
    PlanningResult, PlanningState, PlanningStrategy, PlanningTermination,
    SearchLimits, TemporalPlan,
)
from .constraints import can_fire
from .cost import CostModel
from .state import canonical_state_id
from .transitions import Transition


class TemporalPlanner:
    def __init__(self, cost_model: CostModel | None = None, clock=None):
        self.cost_model = cost_model or CostModel()
        self.clock = clock or time.monotonic

    def plan(self, request, initial_state: PlanningState, model: dict, facts: dict,
             limits: SearchLimits) -> PlanningResult:
        target_id = request if isinstance(request, str) else request.target_element
        transitions = tuple(Transition.from_dict(item) for item in model.get("transitions", ()))
        requested = tuple(item for item in transitions if item.transition_id == target_id)
        run_id = hashlib.sha256(
            f"{initial_state.state_id}:{target_id}:{limits}".encode()).hexdigest()[:20]
        if not requested:
            return PlanningResult(run_id, PlanningTermination.INFEASIBLE, None, (), 0,
                                  ({"code": "TARGET_TRANSITION_MISSING"},))

        location = initial_state.marking[0] if initial_state.marking else ""
        resources = dict(initial_state.resources)
        releases = sorted(facts.get("resource_releases", ()), key=lambda item: float(item["at"]))
        supplied_resources = set(resources)
        supplied_resources.update(str(item["resource"]) for item in releases)
        supplied_resources.update(
            name
            for transition in transitions
            for name, delta in transition.resource_delta.items()
            if delta > 0
        )
        missing = sorted({
            name
            for transition in requested
            for name in transition.requires
            if name not in supplied_resources
        })
        if missing and all(any(name in transition.requires for name in missing)
                           for transition in requested):
            return PlanningResult(
                run_id, PlanningTermination.MISSING_DATA, None, (), 0,
                tuple({"code": "RESOURCE_FACT_MISSING", "resource": name}
                      for name in missing),
            )

        candidates: list[TemporalPlan] = []
        candidate_keys: set[tuple[str, ...]] = set()
        for transition in requested:
            if can_fire(transition, location, resources):
                plan = self._make_plan(run_id, PlanningStrategy.CURRENT, initial_state.state_id,
                                       transition.target, (transition.transition_id,),
                                       transition.duration, transition.budget, transition.risk)
                candidates.append(plan)
                candidate_keys.add(plan.transitions)

        started = self.clock()
        counter = itertools.count()
        # priority, insertion, location, resources, time, budget, risk, path, used_reverse
        queue = [(0.0, next(counter), location, resources, 0.0, 0.0, 0.0, (), False)]
        visited: set[tuple] = set()
        explored = 0
        while queue:
            if self.clock() - started >= limits.timeout_seconds:
                if candidates:
                    return self._select(run_id, candidates, explored,
                                        ({"code": "SEARCH_TIMEOUT_WITH_CANDIDATES"},))
                return PlanningResult(run_id, PlanningTermination.TIMEOUT, None, (), explored)
            if explored >= limits.max_states:
                if candidates:
                    return self._select(run_id, candidates, explored,
                                        ({"code": "SEARCH_LIMIT_WITH_CANDIDATES"},))
                return PlanningResult(run_id, PlanningTermination.EXHAUSTED, None, (), explored)
            _, _, current, available, elapsed, budget, risk, path, used_reverse = heapq.heappop(queue)
            key = (current, tuple(sorted(available.items())), elapsed, used_reverse)
            if key in visited:
                continue
            visited.add(key); explored += 1
            if len(path) >= limits.max_depth:
                continue

            for transition in requested:
                if can_fire(transition, current, available):
                    total_time = elapsed + transition.duration
                    total_budget = budget + transition.budget
                    total_risk = risk + transition.risk
                    full_path = path + (transition.transition_id,)
                    strategy = PlanningStrategy.BACKWARD if used_reverse else PlanningStrategy.FORWARD
                    plan = self._make_plan(run_id, strategy, initial_state.state_id,
                                           transition.target, full_path, total_time,
                                           total_budget, total_risk)
                    if full_path not in candidate_keys:
                        candidates.append(plan)
                        candidate_keys.add(full_path)

            for transition in transitions:
                if transition in requested or not can_fire(transition, current, available):
                    continue
                updated = dict(available)
                for name, delta in transition.resource_delta.items():
                    updated[name] = updated.get(name, 0.0) + delta
                nt, nb, nr = elapsed + transition.duration, budget + transition.budget, risk + transition.risk
                score = self.cost_model.evaluate(nt, nb, nr).weighted_score
                heapq.heappush(queue, (score, next(counter), transition.target, updated,
                                      nt, nb, nr, path + (transition.transition_id,), used_reverse))

            for transition in transitions:
                if transition.reversible and transition.target == current:
                    nt, nb, nr = elapsed + transition.duration, budget, risk + transition.risk
                    score = self.cost_model.evaluate(nt, nb, nr).weighted_score
                    heapq.heappush(queue, (score, next(counter), transition.source, dict(available),
                                          nt, nb, nr, path + (f"reverse:{transition.transition_id}",), True))

            for release in releases:
                at = float(release["at"])
                if at <= elapsed:
                    continue
                updated = dict(available)
                name = str(release["resource"])
                updated[name] = updated.get(name, 0.0) + float(release["amount"])
                score = self.cost_model.evaluate(at, budget, risk).weighted_score
                heapq.heappush(queue, (score, next(counter), current, updated, at, budget, risk,
                                      path + (f"wait:{at:g}",), used_reverse))

        if candidates:
            return self._select(run_id, candidates, explored)
        return PlanningResult(run_id, PlanningTermination.INFEASIBLE, None, (), explored)

    @staticmethod
    def _dominates(left: TemporalPlan, right: TemporalPlan) -> bool:
        left_values = (left.cost.time, left.cost.budget, left.cost.risk)
        right_values = (right.cost.time, right.cost.budget, right.cost.risk)
        return (all(a <= b for a, b in zip(left_values, right_values))
                and any(a < b for a, b in zip(left_values, right_values)))

    def _select(self, run_id: str, candidates: list[TemporalPlan], explored: int,
                diagnostics=()) -> PlanningResult:
        frontier = [candidate for candidate in candidates
                    if not any(self._dominates(other, candidate)
                               for other in candidates if other is not candidate)]
        strategy_order = {
            PlanningStrategy.CURRENT: 0,
            PlanningStrategy.BACKWARD: 1,
            PlanningStrategy.FORWARD: 2,
        }
        frontier.sort(key=lambda item: (
            item.cost.weighted_score,
            strategy_order[item.strategy],
            item.transitions,
            item.plan_id,
        ))
        selected = frontier[0]
        return PlanningResult(run_id, PlanningTermination.FEASIBLE, selected,
                              tuple(frontier), explored, tuple(diagnostics))

    def _make_plan(self, run_id, strategy, start_id, target, path, elapsed, budget, risk):
        cost = self.cost_model.evaluate(elapsed, budget, risk)
        final_id = canonical_state_id(target, {}, elapsed, budget, risk)
        plan_id = hashlib.sha256(f"{run_id}:{strategy.value}:{path}".encode()).hexdigest()[:20]
        return TemporalPlan(plan_id, strategy, start_id, final_id, tuple(path), (), (), cost,
                            True, f"{strategy.value.lower()} plan selected by weighted cost")

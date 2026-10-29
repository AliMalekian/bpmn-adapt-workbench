"""Immutable contracts for temporal state-space planning."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .models import Serializable


class PlanningStrategy(str, Enum):
    CURRENT = "CURRENT"
    BACKWARD = "BACKWARD"
    FORWARD = "FORWARD"


class PlanningTermination(str, Enum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    EXHAUSTED = "EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    MISSING_DATA = "MISSING_DATA"


@dataclass(frozen=True)
class SearchLimits(Serializable):
    max_states: int = 10_000
    max_depth: int = 100
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class PlanningState(Serializable):
    state_id: str
    process_version_id: str
    instance_id: str
    marking: tuple[str, ...]
    completed_elements: tuple[str, ...]
    variables: dict[str, Any]
    resources: dict[str, float]
    logical_time: float
    budget_spent: float
    risk: tuple[float, ...]
    parent_state_id: str | None = None
    transition_id: str | None = None


@dataclass(frozen=True)
class CostBreakdown(Serializable):
    time: float
    budget: float
    risk: float
    weighted_score: float
    normalized: dict[str, float]


@dataclass(frozen=True)
class TemporalPlan(Serializable):
    plan_id: str
    strategy: PlanningStrategy
    start_state_id: str
    final_state_id: str
    transitions: tuple[str, ...]
    satisfied_constraints: tuple[str, ...]
    failed_constraints: tuple[str, ...]
    cost: CostBreakdown
    pareto_optimal: bool
    explanation: str


@dataclass(frozen=True)
class PlanningResult(Serializable):
    planner_run_id: str
    termination: PlanningTermination
    selected_plan: TemporalPlan | None
    alternatives: tuple[TemporalPlan, ...] = ()
    explored_states: int = 0
    diagnostics: tuple[dict[str, Any], ...] = ()

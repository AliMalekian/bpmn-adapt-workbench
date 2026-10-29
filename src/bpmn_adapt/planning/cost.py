"""Versionable time/budget/risk objective."""
from __future__ import annotations

from bpmn_adapt.domain.planning import CostBreakdown


class CostModel:
    def __init__(self, weights=None, bounds=None):
        self.weights = weights or {"time": 0.4, "budget": 0.3, "risk": 0.3}
        self.bounds = bounds or {"time": 100.0, "budget": 100.0, "risk": 1.0}
        if abs(sum(self.weights.values()) - 1.0) > 1e-9:
            raise ValueError("Cost weights must sum to 1")

    def evaluate(self, time: float, budget: float, risk: float) -> CostBreakdown:
        raw = {"time": float(time), "budget": float(budget), "risk": float(risk)}
        normalized = {name: min(1.0, max(0.0, raw[name] / max(float(self.bounds[name]), 1e-12)))
                      for name in raw}
        score = sum(self.weights[name] * normalized[name] for name in normalized)
        return CostBreakdown(raw["time"], raw["budget"], raw["risk"], score, normalized)

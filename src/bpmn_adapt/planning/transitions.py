"""Typed transition parsing for temporal search."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Transition:
    transition_id: str
    source: str
    target: str
    duration: float = 0.0
    budget: float = 0.0
    risk: float = 0.0
    requires: dict[str, float] = field(default_factory=dict)
    resource_delta: dict[str, float] = field(default_factory=dict)
    reversible: bool = False

    @classmethod
    def from_dict(cls, item: dict):
        return cls(str(item["id"]), str(item["source"]), str(item["target"]),
                   float(item.get("duration", 0)), float(item.get("budget", 0)),
                   float(item.get("risk", 0)),
                   {str(k): float(v) for k, v in item.get("requires", {}).items()},
                   {str(k): float(v) for k, v in item.get("resource_delta", {}).items()},
                   bool(item.get("reversible", False)))

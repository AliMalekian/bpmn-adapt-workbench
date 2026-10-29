"""Deterministic resource constraint evaluation."""
from __future__ import annotations

from .transitions import Transition


def missing_resources(transition: Transition, resources: dict[str, float]) -> dict[str, float]:
    return {name: amount - resources.get(name, 0.0)
            for name, amount in transition.requires.items()
            if resources.get(name, 0.0) < amount}


def can_fire(transition: Transition, location: str, resources: dict[str, float]) -> bool:
    return transition.source == location and not missing_resources(transition, resources)

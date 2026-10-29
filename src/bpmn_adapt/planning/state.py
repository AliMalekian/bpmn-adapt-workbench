"""Canonical planner-state helpers."""
from __future__ import annotations

import hashlib
import json


def canonical_state_id(location: str, resources: dict[str, float], logical_time: float,
                       budget: float, risk: float) -> str:
    payload = json.dumps({"location": location, "resources": resources, "time": logical_time,
                          "budget": budget, "risk": risk}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:20]

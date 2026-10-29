"""Deterministic offline LLM used by tests and reproducible experiments."""
from __future__ import annotations
import copy
from typing import Any


class MockLLMClient:
    def __init__(self, fixtures: dict[str, dict[str, Any]] | None = None):
        self.fixtures = fixtures or {
            "normalise_request": {"operation": "REMOVE", "target_element": "", "confidence": 1.0},
            "analyse": {"status": "APPROVE", "reason": "Deterministic mock approval"},
            "model": {"changes": []},
            "experiment": {"passed": True},
            "orchestrate": {"action": "continue"},
        }

    def complete(self, system_prompt: str, user_payload: str, *, schema_name: str) -> dict[str, Any]:
        if schema_name not in self.fixtures:
            raise KeyError(f"No mock fixture for schema {schema_name}")
        if schema_name == "analyse" and self.fixtures[schema_name].get("status") == "APPROVE":
            import json
            try:
                data = json.loads(user_payload)
                req = data.get("adaptation_request", {})
                target = (req.get("target_element") or "").casefold()
                rules = data.get("operational_rules", [])
                conflicts = [r["rule_id"] for r in rules if target and target in r.get("text", "").casefold()]
                if conflicts:
                    return {
                        "status": "REJECT",
                        "reason": f"Operational rule violation: {conflicts}",
                        "rule_ids": conflicts,
                        "resource_ids": [],
                        "rejection_category": "RULE_VIOLATION",
                    }
            except Exception:
                pass
        return copy.deepcopy(self.fixtures[schema_name])


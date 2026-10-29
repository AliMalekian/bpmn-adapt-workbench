"""Opt-in readiness gate for configured external services."""
from __future__ import annotations

import os
import unittest

from bpmn_adapt.config import Settings
from bpmn_adapt.health import probe_all


@unittest.skipUnless(
    os.environ.get("ADAPT_RUN_LIVE_HEALTH") == "1",
    "ADAPT_RUN_LIVE_HEALTH=1 is required for external readiness probes",
)
class LiveServiceHealthTests(unittest.TestCase):
    def test_every_enabled_live_capability_is_ready(self) -> None:
        statuses = probe_all(Settings.from_env())
        failures = [item.to_dict() for item in statuses if item.status not in {
            "READY_OFFLINE", "READY_LIVE", "DISABLED"}]
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from bpmn_adapt.providers.manager import ProviderManager


class ProviderPriorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.close()
        self.path = Path(self.tmp.name)
        data = {
            "providers": [
                {"id": "p1", "name": "Provider 1", "priority": 1, "enabled": True, "api_key": "k1"},
                {"id": "p2", "name": "Provider 2", "priority": 2, "enabled": True, "api_key": "k2"},
                {"id": "p3", "name": "Provider 3", "priority": 3, "enabled": False, "api_key": ""},
                {"id": "p4", "name": "Provider 4", "priority": 4, "enabled": False, "api_key": ""},
            ],
            "fallback_policy": {}
        }
        self.path.write_text(json.dumps(data), encoding="utf-8")
        self.mgr = ProviderManager(config_path=self.path)

    def tearDown(self):
        try:
            self.path.unlink()
        except Exception:
            pass

    def test_reorder_shift_to_top(self):
        # Move p3 to priority 1
        self.mgr.reorder_priority("p3", 1)
        provs = self.mgr.list()
        # Order should be p3(1), p1(2), p2(3), p4(4)
        ids = [p["id"] for p in provs]
        prios = [p["priority"] for p in provs]
        self.assertEqual(ids, ["p3", "p1", "p2", "p4"])
        self.assertEqual(prios, [1, 2, 3, 4])

    def test_reorder_shift_down(self):
        # Move p1 to priority 3
        self.mgr.reorder_priority("p1", 3)
        provs = self.mgr.list()
        # Order should be p2(1), p3(2), p1(3), p4(4)
        ids = [p["id"] for p in provs]
        prios = [p["priority"] for p in provs]
        self.assertEqual(ids, ["p2", "p3", "p1", "p4"])
        self.assertEqual(prios, [1, 2, 3, 4])

    def test_update_priority_triggers_shift(self):
        self.mgr.update("p4", {"priority": 2})
        provs = self.mgr.list()
        # p4 moves to 2, p2 shifts to 3, p3 to 4
        ids = [p["id"] for p in provs]
        self.assertEqual(ids, ["p1", "p4", "p2", "p3"])
        self.assertEqual([p["priority"] for p in provs], [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()

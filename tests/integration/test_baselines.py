from __future__ import annotations
import unittest

from bpmn_adapt.evaluation.baselines import BaselineRunner, BaselineVariant


class BaselineTests(unittest.TestCase):
    def test_all_variants_share_manifest_and_change_only_declared_components(self):
        calls=[]
        def execute(**kwargs): calls.append(kwargs); return {"decision":"PASS","latency":.1}
        runner=BaselineRunner(execute)
        manifest={"dataset":"d","scenario":"s","seed":42}
        results=[runner.run(variant,"s",{"manifest":manifest}) for variant in BaselineVariant]
        self.assertEqual({item.manifest_hash for item in results}.__len__(),1)
        self.assertEqual({item.variant for item in results},set(BaselineVariant))
        conversational=next(call for call in calls if call["variant"] is BaselineVariant.CONVERSATIONAL)
        self.assertFalse(conversational["use_agents"])
        no_sim=next(call for call in calls if call["variant"] is BaselineVariant.NO_SIMULATION)
        self.assertFalse(no_sim["use_simulation"])


if __name__ == "__main__": unittest.main()

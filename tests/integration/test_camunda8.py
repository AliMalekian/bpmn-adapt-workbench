from __future__ import annotations
import os
import unittest


@unittest.skipUnless(os.environ.get("ADAPT_TEST_CAMUNDA_URL"),
                     "pending external resource: live Camunda 8 URL")
class CamundaLiveTests(unittest.TestCase):
    def test_live_health_deploy_instance_and_cleanup(self):
        from bpmn_adapt.engine.http import CamundaHttpTransport
        from bpmn_adapt.engine.camunda8 import Camunda8EngineAdapter
        from tests.unit.test_bpmn_semantics import VALID
        transport=CamundaHttpTransport(os.environ["ADAPT_TEST_CAMUNDA_URL"],rate_limit_per_minute=600)
        engine=Camunda8EngineAdapter(transport)
        self.assertTrue(engine.health().ready)
        deployment=engine.deploy(VALID,"live-test","live-deploy")
        instance=engine.create_instance(deployment.process_definition_key,{"_adapt_run_id":"live-test"},"live-instance")
        self.assertEqual(instance.definition_key,deployment.process_definition_key)
        engine.cleanup("live-test"); transport.close()


if __name__ == "__main__": unittest.main()

"""Workflow-engine contract tests using the deterministic dry-run adapter."""
from __future__ import annotations

import unittest

from bpmn_adapt.engine.dry_run import DryRunEngineAdapter
from bpmn_adapt.engine.contracts import EngineAdapterError
from tests.unit.test_bpmn_semantics import VALID


class EngineAdapterContractTests(unittest.TestCase):
    def setUp(self): self.engine = DryRunEngineAdapter()

    def test_full_deploy_instance_migration_and_scoped_cleanup(self):
        self.assertTrue(self.engine.health().ready)
        deployment = self.engine.deploy(VALID, "run-1", "deploy-1")
        duplicate = self.engine.deploy(VALID, "run-1", "deploy-1")
        self.assertEqual(deployment, duplicate)
        instance = self.engine.create_instance(deployment.process_definition_key, {}, "instance-1")
        state = self.engine.inspect(instance.instance_id)
        validation = self.engine.validate_migration(instance.instance_id,
                                                     deployment.process_definition_key, {})
        self.assertTrue(validation.valid)
        receipt = self.engine.migrate(instance.instance_id,
                                      deployment.process_definition_key, {}, "migrate-1")
        self.assertEqual(receipt, self.engine.migrate(
            instance.instance_id, deployment.process_definition_key, {}, "migrate-1"))
        self.assertEqual(self.engine.inspect(instance.instance_id).definition_key,
                         deployment.process_definition_key)
        self.assertEqual(self.engine.cleanup("different-run").deleted_ids, ())
        self.assertIn(instance.instance_id, self.engine.cleanup("run-1").deleted_ids)

    def test_invalid_mapping_is_rejected_without_side_effect(self):
        deployment = self.engine.deploy(VALID, "run", "d")
        instance = self.engine.create_instance(deployment.process_definition_key, {}, "i")
        with self.assertRaises(EngineAdapterError):
            self.engine.migrate(instance.instance_id, deployment.process_definition_key,
                                {"missing": "also-missing"}, "m")
        self.assertEqual(self.engine.inspect(instance.instance_id).definition_key,
                         deployment.process_definition_key)


if __name__ == "__main__": unittest.main()

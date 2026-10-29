"""Deterministic, stateful offline implementation of the engine contract."""
from __future__ import annotations

import hashlib
import uuid
import xml.etree.ElementTree as ET

from .contracts import (CleanupReceipt, DeploymentReceipt, EngineAdapterError,
                        EngineHealth, InstanceReceipt, InstanceState,
                        MigrationReceipt, MigrationValidation)


class DryRunEngineAdapter:
    def __init__(self):
        self.deployments, self.instances, self.idempotency = {}, {}, {}

    def health(self): return EngineHealth(True, "dry-run-v1", "in-memory deterministic adapter")

    def deploy(self, bpmn_xml, run_id, idempotency_key):
        cached = self.idempotency.get(("deploy", idempotency_key))
        if cached: return cached
        root = ET.fromstring(bpmn_xml)
        process = next((e for e in root.iter() if _local(e) == "process"), None)
        if process is None: raise EngineAdapterError("No BPMN process", code="DEPLOYMENT_INVALID")
        digest = hashlib.sha256(bpmn_xml.encode()).hexdigest()
        receipt = DeploymentReceipt("dry-deploy-" + digest[:16], "dry-def-" + digest[:16],
                                    process.get("id", "process"), run_id, digest)
        nodes = {e.get("id") for e in process.iter() if e.get("id")}
        starts = tuple(e.get("id") for e in process.iter() if _local(e) == "startEvent")
        self.deployments[receipt.process_definition_key] = {
            "receipt": receipt, "nodes": nodes, "starts": starts}
        self.idempotency[("deploy", idempotency_key)] = receipt
        return receipt

    def create_instance(self, definition_key, variables, idempotency_key):
        cached = self.idempotency.get(("instance", idempotency_key))
        if cached: return cached
        deployment = self.deployments.get(definition_key)
        if not deployment: raise EngineAdapterError("Unknown definition", code="DEFINITION_NOT_FOUND")
        instance_id = "dry-instance-" + uuid.uuid5(uuid.NAMESPACE_URL, idempotency_key).hex[:16]
        run_id = deployment["receipt"].run_id
        receipt = InstanceReceipt(instance_id, definition_key, run_id)
        self.instances[instance_id] = {"definition": definition_key,
            "active": deployment["starts"], "variables": dict(variables), "run_id": run_id}
        self.idempotency[("instance", idempotency_key)] = receipt
        return receipt

    def inspect(self, instance_id):
        state = self.instances.get(instance_id)
        if not state: raise EngineAdapterError("Unknown instance", code="INSTANCE_NOT_FOUND")
        return InstanceState(instance_id, state["definition"], tuple(state["active"]),
                             dict(state["variables"]), "ACTIVE")

    def validate_migration(self, instance_id, target_definition_key, mappings):
        state = self.instances.get(instance_id); target = self.deployments.get(target_definition_key)
        if not state or not target:
            return MigrationValidation(False, ({"code": "ENGINE_RESOURCE_NOT_FOUND"},))
        invalid = [(source, destination) for source, destination in mappings.items()
                   if source not in state["active"] or destination not in target["nodes"]]
        return MigrationValidation(not invalid, tuple(
            {"code": "INVALID_ELEMENT_MAPPING", "source": s, "target": t} for s, t in invalid))

    def migrate(self, instance_id, target_definition_key, mappings, idempotency_key):
        cached = self.idempotency.get(("migration", idempotency_key))
        if cached: return cached
        validation = self.validate_migration(instance_id, target_definition_key, mappings)
        if not validation.valid:
            raise EngineAdapterError("Invalid migration mapping", code="MIGRATION_INVALID")
        state = self.instances[instance_id]
        state["active"] = tuple(mappings.get(item, item) for item in state["active"])
        state["definition"] = target_definition_key
        receipt = MigrationReceipt("dry-migration-" + uuid.uuid5(
            uuid.NAMESPACE_URL, idempotency_key).hex[:16], instance_id,
            target_definition_key, idempotency_key, "MIGRATED")
        self.idempotency[("migration", idempotency_key)] = receipt
        return receipt

    def cleanup(self, run_id):
        deleted = tuple(sorted(key for key, value in self.instances.items()
                               if value["run_id"] == run_id))
        for key in deleted: del self.instances[key]
        return CleanupReceipt(run_id, deleted)


def _local(element): return element.tag.rsplit("}", 1)[-1]

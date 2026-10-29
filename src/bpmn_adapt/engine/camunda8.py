"""Camunda 8.8 Orchestration Cluster REST engine adapter."""
from __future__ import annotations

import hashlib
import json
import uuid
import xml.etree.ElementTree as ET

from .contracts import (CleanupReceipt, DeploymentReceipt, EngineAdapterError,
                        EngineHealth, InstanceReceipt, InstanceState,
                        MigrationReceipt, MigrationValidation)


class Camunda8EngineAdapter:
    def __init__(self, transport, *, tenant_id="<default>"):
        self.transport, self.tenant_id = transport, tenant_id
        self._idempotency, self._owned_instances, self._definitions = {}, {}, {}

    def health(self):
        try:
            response = self.transport.request("GET", "/v2/topology")
            return EngineHealth(True, str(response.payload.get("version", "8.8")), "reachable")
        except EngineAdapterError as exc:
            return EngineHealth(False, None, f"{exc.code}: {exc}")

    def deploy(self, bpmn_xml, run_id, idempotency_key):
        cached = self._idempotency.get(("deploy", idempotency_key))
        if cached: return cached
        request_hash = hashlib.sha256(bpmn_xml.encode()).hexdigest()
        resource_name = f"adapt-{idempotency_key}-{request_hash[:8]}.bpmn"
        try:
            response = self.transport.request("POST", "/v2/deployments",
                files={"resources": (resource_name, bpmn_xml.encode(), "application/xml")},
                json=None, idempotency_key=idempotency_key)
            receipt = self._deployment_receipt(response.payload, run_id, request_hash)
        except EngineAdapterError as exc:
            if not exc.retryable: raise
            receipt = self._reconcile_deployment(resource_name, run_id, request_hash)
            if receipt is None: raise
        self._idempotency[("deploy", idempotency_key)] = receipt
        self._definitions[receipt.process_definition_key] = _node_ids(bpmn_xml)
        return receipt

    def _reconcile_deployment(self, resource_name, run_id, request_hash):
        response = self.transport.request("POST", "/v2/process-definitions/search",
                                          json={"filter": {"resourceName": resource_name}})
        items = response.payload.get("items", [])
        if not items: return None
        item = items[0]
        return DeploymentReceipt(str(item.get("deploymentKey", "reconciled")),
            str(item["processDefinitionKey"]), str(item["processDefinitionId"]), run_id,
            request_hash, {"reconciled": True})

    @staticmethod
    def _deployment_receipt(payload, run_id, request_hash):
        definitions = [item["processDefinition"] for item in payload.get("deployments", [])
                       if item.get("processDefinition")]
        if not definitions: raise EngineAdapterError("Deployment returned no process definition",
                                                     code="DEPLOYMENT_INVALID")
        item = definitions[0]
        return DeploymentReceipt(str(payload["deploymentKey"]),
            str(item["processDefinitionKey"]), str(item["processDefinitionId"]), run_id,
            request_hash, {"tenantId": payload.get("tenantId")})

    def create_instance(self, definition_key, variables, idempotency_key):
        cached = self._idempotency.get(("instance", idempotency_key))
        if cached: return cached
        response = self.transport.request("POST", "/v2/process-instances", json={
            "processDefinitionKey": definition_key, "variables": variables,
            "tenantId": self.tenant_id}, idempotency_key=idempotency_key)
        instance_id = str(response.payload["processInstanceKey"])
        run_id = str(variables.get("_adapt_run_id", ""))
        receipt = InstanceReceipt(instance_id, definition_key, run_id)
        self._owned_instances[instance_id] = run_id
        self._idempotency[("instance", idempotency_key)] = receipt
        return receipt

    def inspect(self, instance_id):
        response = self.transport.request("POST", "/v2/process-instances/search",
                                          json={"filter": {"processInstanceKey": instance_id}})
        items = response.payload.get("items", [])
        if not items: raise EngineAdapterError("Instance not found", code="INSTANCE_NOT_FOUND")
        item = items[0]
        active = tuple(sorted(item.get("activeElementIds", ())))
        return InstanceState(instance_id, str(item.get("processDefinitionKey", "")), active,
                             dict(item.get("variables", {})), str(item.get("state", "ACTIVE")))

    def validate_migration(self, instance_id, target_definition_key, mappings):
        state = self.inspect(instance_id)
        target_nodes = self._definitions.get(target_definition_key)
        diagnostics = []
        if target_nodes is None: diagnostics.append({"code": "TARGET_DEFINITION_UNKNOWN"})
        for source, target in mappings.items():
            if state.active_elements and source not in state.active_elements:
                diagnostics.append({"code": "SOURCE_NOT_ACTIVE", "source": source})
            if target_nodes is not None and target not in target_nodes:
                diagnostics.append({"code": "TARGET_ELEMENT_UNKNOWN", "target": target})
        return MigrationValidation(not diagnostics, tuple(diagnostics))

    def migrate(self, instance_id, target_definition_key, mappings, idempotency_key):
        cached = self._idempotency.get(("migration", idempotency_key))
        if cached: return cached
        validation = self.validate_migration(instance_id, target_definition_key, mappings)
        if not validation.valid:
            raise EngineAdapterError("Invalid migration mapping", code="MIGRATION_INVALID")
        instructions = [{"sourceElementId": source, "targetElementId": target}
                        for source, target in sorted(mappings.items())]
        try:
            self.transport.request("POST", f"/v2/process-instances/{instance_id}/migration",
                json={"targetProcessDefinitionKey": target_definition_key,
                      "mappingInstructions": instructions}, idempotency_key=idempotency_key)
        except EngineAdapterError as exc:
            if not exc.retryable or self.inspect(instance_id).definition_key != target_definition_key:
                raise
        post = self.inspect(instance_id)
        if post.definition_key != target_definition_key:
            raise EngineAdapterError("Post-migration definition mismatch", code="MIGRATION_VERIFY_FAILED")
        receipt = MigrationReceipt(str(uuid.uuid4()), instance_id, target_definition_key,
                                   idempotency_key, "MIGRATED")
        self._idempotency[("migration", idempotency_key)] = receipt
        return receipt

    def cleanup(self, run_id):
        targets = tuple(sorted(key for key, owner in self._owned_instances.items() if owner == run_id))
        for instance_id in targets:
            self.transport.request("DELETE", f"/v2/process-instances/{instance_id}")
            del self._owned_instances[instance_id]
        return CleanupReceipt(run_id, targets)


def _node_ids(xml):
    root = ET.fromstring(xml)
    return {str(item.get("id")) for item in root.iter()
            if item.get("id") and item.tag.rsplit("}", 1)[-1] != "sequenceFlow"}

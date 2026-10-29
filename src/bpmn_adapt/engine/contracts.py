"""Engine-neutral protocol and sanitized immutable receipts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class EngineAdapterError(RuntimeError):
    def __init__(self, message, *, code="ENGINE_ERROR", retryable=False):
        super().__init__(message); self.code, self.retryable = code, retryable


@dataclass(frozen=True)
class EngineHealth: ready: bool; version: str | None; detail: str
@dataclass(frozen=True)
class DeploymentReceipt:
    deployment_id: str; process_definition_key: str; process_id: str
    run_id: str; request_hash: str; raw: dict[str, Any] | None = None
@dataclass(frozen=True)
class InstanceReceipt: instance_id: str; definition_key: str; run_id: str
@dataclass(frozen=True)
class InstanceState:
    instance_id: str; definition_key: str; active_elements: tuple[str, ...]
    variables: dict[str, Any]; status: str
@dataclass(frozen=True)
class MigrationValidation: valid: bool; diagnostics: tuple[dict[str, Any], ...] = ()
@dataclass(frozen=True)
class MigrationReceipt:
    migration_id: str; instance_id: str; target_definition_key: str
    idempotency_key: str; status: str
@dataclass(frozen=True)
class CleanupReceipt: run_id: str; deleted_ids: tuple[str, ...]


class WorkflowEngineAdapter(Protocol):
    def health(self) -> EngineHealth: ...
    def deploy(self, bpmn_xml: str, run_id: str, idempotency_key: str) -> DeploymentReceipt: ...
    def create_instance(self, definition_key: str, variables: dict,
                        idempotency_key: str) -> InstanceReceipt: ...
    def inspect(self, instance_id: str) -> InstanceState: ...
    def validate_migration(self, instance_id: str, target_definition_key: str,
                           mappings: dict[str, str]) -> MigrationValidation: ...
    def migrate(self, instance_id: str, target_definition_key: str,
                mappings: dict[str, str], idempotency_key: str) -> MigrationReceipt: ...
    def cleanup(self, run_id: str) -> CleanupReceipt: ...

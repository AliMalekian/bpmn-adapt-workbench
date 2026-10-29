"""Engine-neutral deployment and migration records."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .models import Serializable


class EngineStatus(str, Enum):
    PLANNED = "PLANNED"
    VALIDATED = "VALIDATED"
    DEPLOYED = "DEPLOYED"
    MIGRATED = "MIGRATED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class EngineDeployment(Serializable):
    deployment_id: str
    run_id: str
    engine_type: str
    remote_key: str | None
    process_definition_key: str | None
    status: EngineStatus
    request_hash: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class EngineMigrationReceipt(Serializable):
    migration_id: str
    run_id: str
    instance_id: str
    idempotency_key: str
    status: EngineStatus
    source_definition_key: str
    target_definition_key: str
    active_elements: tuple[str, ...] = ()
    variables_checksum: str | None = None

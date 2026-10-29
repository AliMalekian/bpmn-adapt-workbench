"""Serializable contracts for formal verification gates."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from bpmn_adapt.domain.models import Serializable


class FormalStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class CheckerReport(Serializable):
    status: FormalStatus
    version: str | None
    exit_code: int | None
    duration_seconds: float
    payload: dict[str, Any] = field(default_factory=dict)
    diagnostics: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class FormalReport(Serializable):
    status: FormalStatus
    pnml_path: str | None
    pnml_checksum: str | None
    properties: dict[str, Any]
    diagnostics: tuple[dict[str, Any], ...]
    backend: str
    backend_version: str | None
    duration_seconds: float

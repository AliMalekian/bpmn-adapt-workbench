"""Common validator result envelope used by every quality gate."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import Serializable


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    UNSUPPORTED = "UNSUPPORTED"


class DiagnosticSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ValidationDiagnostic(Serializable):
    code: str
    severity: DiagnosticSeverity
    message: str
    element_ids: tuple[str, ...] = ()
    citation: str | None = None


@dataclass(frozen=True)
class ValidationReport(Serializable):
    validation_id: str
    validator_id: str
    validator_version: str
    status: ValidationStatus
    diagnostics: tuple[ValidationDiagnostic, ...]
    input_checksum: str
    output_checksum: str | None
    duration_seconds: float
    reproduction_command: str


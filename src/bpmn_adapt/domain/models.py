"""Shared, serialisable contracts passed between components.

The contracts intentionally use standard-library dataclasses so offline and
reproduction environments do not need an external validation framework.
Boundary services validate required invariants when constructing them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Serializable:
    def to_dict(self) -> dict[str, Any]:
        def encode(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, Path):
                return str(value)
            if hasattr(value, "to_dict"):
                return value.to_dict()
            if isinstance(value, dict):
                return {str(k): encode(v) for k, v in value.items()}
            if isinstance(value, (list, tuple, set)):
                return [encode(v) for v in value]
            return value
        return encode(asdict(self))


class OperationType(str, Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    RE_ADD = "RE_ADD"
    MODIFY = "MODIFY"


class DecisionStatus(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ALTERNATIVE_PROPOSED = "ALTERNATIVE_PROPOSED"


@dataclass(frozen=True)
class Rule(Serializable):
    rule_id: str
    text: str


@dataclass(frozen=True)
class ResourceFact(Serializable):
    resource_id: str
    name: str
    value: str


@dataclass(frozen=True)
class TokenState(Serializable):
    element_id: str
    status: str = "active"


@dataclass(frozen=True)
class RuntimeState(Serializable):
    state_id: str
    current_position: str
    completed_activities: tuple[str, ...] = ()
    tokens: tuple[TokenState, ...] = ()
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessDefinition(Serializable):
    process_id: str
    folder: Path
    name: str
    narrative: str
    bpmn_files: tuple[Path, ...]
    rules: tuple[Rule, ...]
    resources: tuple[ResourceFact, ...]
    states: tuple[RuntimeState, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessVersion(Serializable):
    version_id: str
    process_id: str
    parent_version_id: str | None
    bpmn_xml: str
    checksum: str


@dataclass(frozen=True)
class AdaptationRequest(Serializable):
    request_id: str
    process_id: str
    source_folder: Path
    operation: OperationType
    raw_text: str
    target_element: str
    source_version_id: str | None = None


@dataclass(frozen=True)
class RetrievedEvidence(Serializable):
    evidence_id: str
    process_id: str
    operation: OperationType
    text: str
    decision: str
    semantic_score: float
    syntactic_score: float
    final_score: float
    source_version_id: str | None = None
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeasibilityDecision(Serializable):
    decision_id: str
    status: DecisionStatus
    reason: str
    request: AdaptationRequest
    rule_ids: tuple[str, ...] = ()
    resource_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    proposed_timing: str = "current"
    planning_result: dict[str, Any] | None = None
    rejection_category: str | None = None


@dataclass(frozen=True)
class AtomicChange(Serializable):
    action: OperationType
    target_id: str
    target_name: str
    predecessor_ids: tuple[str, ...] = ()
    successor_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class MigrationPlan(Serializable):
    mappings: dict[str, str]
    safe: bool
    reason: str
    variable_mappings: dict[str, str] = field(default_factory=dict)
    scope_mappings: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateModel(Serializable):
    candidate_id: str
    source_version_id: str
    bpmn_xml: str
    changes: tuple[AtomicChange, ...]
    migration: MigrationPlan
    checksum: str


@dataclass(frozen=True)
class ExperimentScenario(Serializable):
    scenario_id: str
    initial_state: RuntimeState
    expected_result: str


@dataclass(frozen=True)
class ExperimentReport(Serializable):
    report_id: str
    candidate_id: str
    passed: bool
    traces: tuple[tuple[str, ...], ...]
    failures: tuple[dict[str, Any], ...] = ()
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RunProvenance(Serializable):
    run_id: str
    process_id: str
    folder: str
    config_fingerprint: str
    prompt_versions: dict[str, str]
    status: str
    events: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class AdaptationResult(Serializable):
    run_id: str
    status: str
    decision: FeasibilityDecision
    candidate: CandidateModel | None
    experiment: ExperimentReport | None
    provenance: RunProvenance

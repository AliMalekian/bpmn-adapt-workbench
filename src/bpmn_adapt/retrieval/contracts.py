"""Contracts for dense, lexical, and fused retrieval with complete logs."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import numpy as np

from bpmn_adapt.domain.models import Serializable


class RetrievalMode(str, Enum):
    NONE = "none"
    SYNTACTIC = "syntactic"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class VectorScope(Serializable):
    process_id: str | None = None
    operation: str | None = None
    source_version_id: str | None = None
    process_family: str | None = None
    active_only: bool = True

    def filters(self):
        return {key: value for key, value in self.to_dict().items()
                if value is not None}


@dataclass(frozen=True)
class VectorRecord:
    evidence_id: str
    text: str
    vector: np.ndarray
    metadata: dict[str, Any]
    active: bool
    model_key: str


@dataclass(frozen=True)
class VectorHit:
    evidence_id: str
    text: str
    score: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RankedCandidate(Serializable):
    evidence_id: str
    rank: int
    scores: dict[str, float]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RetrievalLog(Serializable):
    retrieval_id: str
    query_hash: str
    mode: RetrievalMode
    filters: dict[str, Any]
    model_key: str
    fusion_version: str
    candidates: tuple[RankedCandidate, ...]


@dataclass(frozen=True)
class RetrievalResult:
    hits: tuple[VectorHit, ...]
    log: RetrievalLog

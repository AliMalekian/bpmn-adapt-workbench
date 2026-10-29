"""Controlled baseline/ablation runner with identical manifest enforcement."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json


class BaselineVariant(str, Enum):
    CONVERSATIONAL="conversational"
    NO_SIMULATION="no_simulation"
    NO_RAG="no_rag"
    SYNTACTIC="syntactic"
    SEMANTIC="semantic"
    HYBRID="hybrid"
    HYBRID_UPDATED="hybrid_updated"


@dataclass(frozen=True)
class BaselineResult:
    variant: BaselineVariant
    scenario_id: str
    manifest_hash: str
    output: dict


class BaselineRunner:
    def __init__(self, executor): self.executor=executor

    def run(self, variant, scenario, context):
        variant=BaselineVariant(variant)
        manifest=json.dumps(context["manifest"],sort_keys=True,separators=(",",":"))
        manifest_hash=hashlib.sha256(manifest.encode()).hexdigest()
        options={
            "variant":variant,
            "scenario":scenario,
            "context":context,
            "use_agents":variant is not BaselineVariant.CONVERSATIONAL,
            "use_simulation":variant is not BaselineVariant.NO_SIMULATION,
            "rag_mode":({BaselineVariant.NO_RAG:"none",BaselineVariant.SYNTACTIC:"syntactic",
                         BaselineVariant.SEMANTIC:"semantic"}.get(variant,"hybrid")),
            "use_updated_rag":variant is BaselineVariant.HYBRID_UPDATED,
        }
        return BaselineResult(variant,str(scenario),manifest_hash,dict(self.executor(**options)))

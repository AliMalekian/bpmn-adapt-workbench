"""Stable application-boundary envelopes shared by CLI and GUI."""
from __future__ import annotations
from dataclasses import dataclass,field
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    command:str; status:str; payload:dict[str,Any]
    run_id:str|None=None; artefacts:tuple[str,...]=(); warnings:tuple[str,...]=()

    def to_dict(self):
        return {"schema_version":"1.0","command":self.command,"status":self.status,
                "run_id":self.run_id,"payload":self.payload,
                "artefacts":list(self.artefacts),"warnings":list(self.warnings)}

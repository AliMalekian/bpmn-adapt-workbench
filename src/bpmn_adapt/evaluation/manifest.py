"""Append-only resumability ledger with checksum-drift awareness."""
from __future__ import annotations
import json
import os
from pathlib import Path
import threading
from datetime import datetime,timezone


class ExperimentManifest:
    def __init__(self,path:Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._lock=threading.Lock()
        self._completed=set(); self._load()
    def _load(self):
        if not self.path.exists(): return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            item=json.loads(line)
            if item.get("status") in {"PASS","FAIL","NOT_EVALUABLE","BLOCKED_EXTERNAL"}:
                self._completed.add((item["folder_id"],item["folder_checksum"],item["scenario_id"],item["variant"],
                                     item.get("experiment_fingerprint",""),item.get("runner_version","v1")))
    def completed(self,folder_id,checksum,scenario_id,variant,*,experiment_fingerprint="",runner_version="v1"):
        return (folder_id,checksum,scenario_id,variant,experiment_fingerprint,runner_version) in self._completed
    def append_result(self,folder_id,folder_checksum,scenario_id,variant,status,payload,*,
                      experiment_fingerprint="",runner_version="v1"):
        event={"timestamp":datetime.now(timezone.utc).isoformat(),"folder_id":folder_id,
               "folder_checksum":folder_checksum,"scenario_id":scenario_id,"variant":variant,
               "experiment_fingerprint":experiment_fingerprint,"runner_version":runner_version,
               "status":status,"payload":payload}
        encoded=json.dumps(event,ensure_ascii=False,sort_keys=True)
        with self._lock:
            with self.path.open("a",encoding="utf-8") as handle:
                handle.write(encoded+"\n"); handle.flush(); os.fsync(handle.fileno())
            self._completed.add((folder_id,folder_checksum,scenario_id,variant,
                                 experiment_fingerprint,runner_version))
        return event

"""Content-addressed dataset discovery and bounded isolated execution."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import dataclass,replace
import hashlib
import json
from pathlib import Path
import re
import threading

from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.ingestion.discovery import ingest_folder


@dataclass(frozen=True)
class DatasetScenario:
    scenario_id:str; kind:str; request:str=""; target:str=""; operation:str|None=None
@dataclass(frozen=True)
class DatasetFolder:
    folder_id:str; path:Path; checksum:str; scenarios:tuple[DatasetScenario,...]
@dataclass(frozen=True)
class InvalidFolder:
    path:Path; reason:str
@dataclass(frozen=True)
class DatasetDiscovery:
    valid:tuple[DatasetFolder,...]; invalid:tuple[InvalidFolder,...]


def discover_dataset(root,recursive=False,prefixes=None):
    root=Path(root).resolve(); iterator=root.rglob("*") if recursive else root.iterdir()
    directories=sorted(path for path in iterator if path.is_dir() and not path.name.startswith("."))
    if recursive: directories=[path for path in directories if not any(child.is_dir() for child in path.iterdir())]
    if prefixes: directories=[path for path in directories if any(path.name.casefold().startswith(p.casefold()) for p in prefixes)]
    valid=[]; invalid=[]
    for folder in directories:
        try:
            bundle=ingest_folder(folder); checksum=_folder_checksum(folder)
            valid.append(DatasetFolder(bundle.definition.process_id,folder,checksum,_scenarios(bundle)))
        except Exception as exc: invalid.append(InvalidFolder(folder,f"{type(exc).__name__}: {exc}"))
    return DatasetDiscovery(tuple(valid),tuple(invalid))


def _folder_checksum(folder):
    digest=hashlib.sha256()
    for path in sorted(item for item in Path(folder).iterdir() if item.is_file()):
        digest.update(path.name.encode()); digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _scenarios(bundle):
    scenarios=[DatasetScenario("inspect","inspect"),DatasetScenario("evaluate","evaluate")]
    blocks=re.split(r"(?mi)(?=^Request\d+:)",bundle.remove_requests)
    for block in blocks:
        match=re.search(r"(?mi)^Request(\d+):",block); target=re.search(r'(?mi)^Removed element:\s*"([^"]+)',block)
        if match and target: scenarios.append(DatasetScenario(f"remove-{match.group(1)}","adapt",block.strip(),target.group(1),"REMOVE"))
    target=re.search(r'(?mi)^Restored element:\s*"([^"]+)',bundle.readd_request)
    if target: scenarios.append(DatasetScenario("re-add","adapt",bundle.readd_request.strip(),target.group(1),"RE_ADD"))
    return tuple(scenarios)


class DatasetExecutor:
    RUNNER_VERSION="dataset-runner-v2"
    def __init__(self,settings,manifest,output_root,max_workers=4):
        self.settings,self.manifest,self.output_root=settings,manifest,Path(output_root)
        self.max_workers=max_workers; self._counts={"completed":0,"failed":0,"skipped":0}; self._lock=threading.Lock()
    def run(self,folders,variants,scenario_kinds=None):
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures=[pool.submit(self._folder,item,tuple(variants),scenario_kinds) for item in folders]
            for future in as_completed(futures): future.result()
        return dict(self._counts)
    def _folder(self,item,variants,kinds):
        namespace=self.output_root/"folders"/item.folder_id; namespace.mkdir(parents=True,exist_ok=True)
        settings=replace(self.settings,database_url=f"sqlite:///{namespace/'runtime.db'}",output_root=namespace/"runs")
        app=RuntimeAdaptationApplication.from_settings(settings)
        try:
            for scenario in item.scenarios:
                if kinds and scenario.kind not in kinds: continue
                for variant in variants:
                    fingerprint=settings.fingerprint()
                    if self.manifest.completed(item.folder_id,item.checksum,scenario.scenario_id,variant,
                                               experiment_fingerprint=fingerprint,
                                               runner_version=self.RUNNER_VERSION): self._add("skipped"); continue
                    try:
                        previous=app.rag.default_mode; app.rag.default_mode=_rag_mode(variant)
                        if scenario.kind=="inspect": payload=app.inspect(item.path)
                        elif scenario.kind=="evaluate": payload=app.evaluate_folder(item.path)
                        else: payload=app.adapt_folder(item.path,scenario.request,target=scenario.target,operation=scenario.operation).to_dict()
                        app.rag.default_mode=previous
                        # A structured rejection/failure is a valid workflow outcome; FAIL is
                        # reserved for an uncaught runner/use-case exception. The underlying
                        # adaptation status remains preserved in the payload for accuracy metrics.
                        status="PASS"
                    except Exception as exc:
                        payload={"error_type":type(exc).__name__,"message":str(exc)}; status="FAIL"
                    self.manifest.append_result(item.folder_id,item.checksum,scenario.scenario_id,variant,status,payload,
                                                experiment_fingerprint=fingerprint,
                                                runner_version=self.RUNNER_VERSION)
                    self._add("completed" if status=="PASS" else "failed")
        finally: app.close()
    def _add(self,key):
        with self._lock:self._counts[key]+=1


def _rag_mode(variant):
    return {"no-rag":"none","none":"none","syntactic":"syntactic","semantic":"semantic"}.get(variant,"hybrid")

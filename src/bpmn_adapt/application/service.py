"""Folder-scoped use cases shared by GUI and CLI."""
from __future__ import annotations
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import uuid
import hashlib
import zipfile

from bpmn_adapt.agents.analyst import AnalystAgent
from bpmn_adapt.agents.orchestrator import OrchestratorAgent
from bpmn_adapt.bpmn.graph import BpmnGraph
from bpmn_adapt.config import Settings
from bpmn_adapt.domain.models import AdaptationRequest, OperationType
from bpmn_adapt.ingestion.discovery import ingest_folder
from bpmn_adapt.llm.embedding import HashEmbeddingClient
from bpmn_adapt.llm.mock import MockLLMClient
from bpmn_adapt.llm.openai_compatible import OpenAICompatibleClient
from bpmn_adapt.persistence import create_database
from bpmn_adapt.retrieval.service import HybridRAGService
from bpmn_adapt.engine.dry_run import DryRunEngineAdapter


class RuntimeAdaptationApplication:
    def __init__(self,settings,database,llm,embedding):
        self.settings=settings; self.database=database; self.llm=llm
        self.rag=HybridRAGService(database,embedding,default_mode=settings.rag_mode)
        self.orchestrator=OrchestratorAgent(database,self.rag,llm,settings)
        self.engine=self._build_engine(settings)

    @staticmethod
    def _build_engine(settings):
        if settings.engine_mode in {"disabled","dry_run"}: return DryRunEngineAdapter()
        from bpmn_adapt.engine.http import CamundaHttpTransport
        from bpmn_adapt.engine.camunda8 import Camunda8EngineAdapter
        transport=CamundaHttpTransport(settings.engine_base_url,oauth_url=settings.engine_oauth_url,
            client_id=settings.engine_client_id,client_secret=settings.engine_client_secret,
            timeout=settings.engine_timeout_seconds,max_retries=settings.engine_max_retries,
            rate_limit_per_minute=settings.rate_limit_per_minute)
        return Camunda8EngineAdapter(transport,tenant_id=settings.engine_tenant_id)

    @classmethod
    def from_settings(cls,settings:Settings):
        if settings.llm_mode != "live":
            raise RuntimeError(
                f"FATAL: Live LLM mode required. Current mode: {settings.llm_mode!r}. "
                "Mock mode is disabled for evaluation."
            )
        database=create_database(settings.database_url); database.initialize()
        from bpmn_adapt.providers.manager import ProviderManager
        from bpmn_adapt.llm.fallback_client import FallbackLLMClient

        prov_mgr = ProviderManager()
        enabled_provs = prov_mgr.enabled_providers()
        if enabled_provs:
            clients = [prov_mgr.build_client(p["id"]) for p in enabled_provs]
            llm = FallbackLLMClient(enabled_provs, clients)
        else:
            llm = OpenAICompatibleClient(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                fallback_model=settings.llm_fallback_model or os.getenv("ADAPT_LLM_FALLBACK_MODEL"),
                fallback_base_url=settings.llm_fallback_base_url or os.getenv("ADAPT_LLM_FALLBACK_BASE_URL"),
                fallback_api_key=settings.llm_fallback_api_key or os.getenv("ADAPT_LLM_FALLBACK_API_KEY"),
                timeout=settings.timeout_seconds,
                max_retries=settings.max_retries,
                backoff=settings.retry_backoff_seconds,
                rate_limit_per_minute=settings.rate_limit_per_minute,
            )
        if settings.embedding_provider == "hash_test":
            return cls(settings,database,llm,HashEmbeddingClient())
        if settings.embedding_provider == "sentence_transformers":
            instance = cls.__new__(cls)
            instance.settings = settings
            instance.database = database
            instance.llm = llm
            instance.rag = HybridRAGService.from_settings(database, settings)
            instance.orchestrator = OrchestratorAgent(database, instance.rag, llm, settings)
            instance.engine = instance._build_engine(settings)
            return instance
        database.close()
        raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")

    def close(self): self.database.close()

    def ingest(self,folder):
        bundle=ingest_folder(folder); d=bundle.definition
        self.database.upsert_process(d.process_id,str(d.folder),d.name,d.narrative,bundle.bpmn_xml,[(r.rule_id,r.text) for r in d.rules],[(r.resource_id,r.name,r.value) for r in d.resources],[(s.state_id,s.current_position,json.dumps(s.to_dict())) for s in d.states])
        import_run=f"import-{d.process_id}"
        if not self.database.get_run(import_run): self.database.create_run(import_run,d.process_id,self.settings.fingerprint(),"approved")
        for index,record in enumerate(bundle.rag_records,1):
            evidence_id=f"source-{d.process_id}-{record.get('id',index)}"
            if self.database.has_rag_case(evidence_id): continue
            operation=record.get("operation_type","REMOVE").replace("RE_ADD","RE_ADD")
            if operation not in {"REMOVE","RE_ADD"}: operation="REMOVE"
            self.database.add_rag_case(evidence_id,import_run,d.process_id,f"{d.process_id}-source",operation,record.get("text",""),record.get("decision","UNKNOWN"),json.dumps({"origin":"RagData.txt","folder":str(d.folder)},sort_keys=True))
        self.rag.index_existing(process_id=d.process_id)
        return bundle

    def _request(self,bundle,text,target=None,operation=None):
        lower=text.casefold()
        if operation: op=OperationType(operation.upper())
        elif any(x in lower for x in ("re-add","readd","restore","restore")): op=OperationType.RE_ADD
        else: op=OperationType.REMOVE
        if not target:
            quoted=re.search(r'[“\"]([^”\"]+)[”\"]',text)
            if quoted: target=quoted.group(1)
            else:
                target=re.sub(r"(?i)^\s*(please\s+)?(remove|delete|re-?add|restore)\s+", "", text).strip()
        return AdaptationRequest(str(uuid.uuid4()),bundle.definition.process_id,bundle.definition.folder,op,text,target or "",f"{bundle.definition.process_id}-source")

    @staticmethod
    def _tokens(bundle,state_id):
        graph=BpmnGraph.from_xml(bundle.bpmn_xml)
        selected=next((s for s in bundle.definition.states if s.state_id==state_id),bundle.definition.states[0] if bundle.definition.states else None)
        if not selected: return set()
        node=graph.nodes.get(selected.current_position) or graph.element_by_name(selected.current_position)
        return {node.element_id} if node else set()

    def analyse_folder(self,folder,text,*,target=None,operation=None,state_id=None):
        bundle=self.ingest(folder); request=self._request(bundle,text,target,operation)
        run_id=str(uuid.uuid4()); self.database.create_run(run_id,request.process_id,self.settings.fingerprint(),"analysis")
        self.database.save_request(run_id,request)
        decision=AnalystAgent(self.database,self.rag,self.llm).analyse(request,run_id=run_id)
        self.database.save_decision(run_id,decision); self.database.update_run_status(run_id,"analysis_complete")
        return decision

    def adapt_folder(self,folder,text,*,target=None,operation=None,state_id=None,run_id=None):
        bundle=self.ingest(folder); request=self._request(bundle,text,target,operation)
        if request.operation==OperationType.RE_ADD:
            latest=self.database.get_latest_version(request.process_id)
            if latest: request=replace(request,source_version_id=latest["version_id"])
        result=self.orchestrator.run(request,active_tokens=self._tokens(bundle,state_id),oracle_bpmn_xml=bundle.bpmn_xml if request.operation==OperationType.RE_ADD else None,run_id=run_id)
        output=self.settings.output_root/result.run_id; output.mkdir(parents=True,exist_ok=True)
        (output/"result.json").write_text(json.dumps(result.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8")
        if result.candidate: (output/"candidate.bpmn").write_text(result.candidate.bpmn_xml,encoding="utf-8")
        return result

    def simulate_folder(self,folder):
        from bpmn_adapt.simulation.engine import simulate
        bundle=self.ingest(folder); traces,failures=simulate(bundle.bpmn_xml)
        return {"process_id":bundle.definition.process_id,"passed":not failures,"traces":[list(x) for x in traces],"failures":list(failures)}

    def evaluate_folder(self,folder):
        from bpmn_adapt.evaluation.runner import EvaluationRunner
        return EvaluationRunner(self).evaluate(folder)

    def report_folder(self,folder):
        bundle=self.ingest(folder); d=bundle.definition
        return {"process":{"process_id":d.process_id,"name":d.name,"folder":str(d.folder),"bpmn_file_count":len(d.bpmn_files),"rule_count":len(d.rules),"resource_count":len(d.resources),"state_count":len(d.states),"rag_example_count":len(bundle.rag_records),"test_case_count":len(bundle.test_cases)},"configuration":{"fingerprint":self.settings.fingerprint(),"rag_mode":self.settings.rag_mode,"llm_mode":self.settings.llm_mode}}

    def index_rag_folder(self,folder):
        bundle=self.ingest(folder)
        indexed=self.rag.index_existing(process_id=bundle.definition.process_id)
        return {"process_id":bundle.definition.process_id,"indexed":indexed or len(bundle.rag_records),
                "persistent":self.rag.vector_store is not None}

    def revoke_rag(self,evidence_id,reason):
        self.rag.revoke(evidence_id,reason); return {"evidence_id":evidence_id,"active":False,"reason":reason}

    def validate_folder(self,folder):
        from bpmn_adapt.bpmn.validation import BpmnValidator
        bundle=self.ingest(folder); return BpmnValidator().validate(bundle.bpmn_xml).to_dict()

    def plan_folder(self,folder,text,*,target=None,state_id=None):
        from bpmn_adapt.domain.planning import PlanningState,SearchLimits
        from bpmn_adapt.planning.temporal import TemporalPlanner
        bundle=self.ingest(folder); graph=BpmnGraph.from_xml(bundle.bpmn_xml)
        requested=graph.resolve_node(target or text)
        selected=next((s for s in bundle.definition.states if s.state_id==state_id),None)
        location=(graph.resolve_node(selected.current_position).element_id if selected and graph.resolve_node(selected.current_position) else next(iter(graph.nodes),""))
        transitions=[{"id":flow.element_id,"source":flow.source_ref,"target":flow.target_ref}
                     for flow in graph.flows.values()]
        if requested:
            transitions.append({"id":requested.element_id,"source":location,"target":requested.element_id})
        state=PlanningState("cli-state",f"{bundle.definition.process_id}-source","cli-instance",(location,),(),{}, {},0,0,(0,))
        return TemporalPlanner().plan(requested.element_id if requested else target or text,state,
            {"transitions":transitions},{},SearchLimits(self.settings.planner_max_states,
            self.settings.planner_max_depth,self.settings.planner_timeout_seconds)).to_dict()

    def deploy_folder(self,folder,*,run_id=None,create_instance=False,variables=None):
        bundle=self.ingest(folder); run_id=run_id or str(uuid.uuid4())
        deployment=self.engine.deploy(bundle.bpmn_xml,run_id,f"deploy:{run_id}:{bundle.definition.process_id}")
        payload={"deployment":deployment.__dict__}
        if create_instance:
            values={**(variables or {}),"_adapt_run_id":run_id}
            payload["instance"]=self.engine.create_instance(deployment.process_definition_key,values,f"instance:{run_id}").__dict__
        return payload

    def migrate_instance(self,instance_id,target_definition_key,mappings,*,run_id=None):
        validation=self.engine.validate_migration(instance_id,target_definition_key,mappings)
        if not validation.valid: raise ValueError(f"Migration invalid: {validation.diagnostics}")
        return self.engine.migrate(instance_id,target_definition_key,mappings,
                                   f"migration:{run_id or 'manual'}:{instance_id}").__dict__

    def inspect(self,folder=None,instance_id=None):
        if instance_id: return self.engine.inspect(instance_id).__dict__
        bundle=self.ingest(folder); pid=bundle.definition.process_id
        return {"process":self.database.get_process(pid),"rules":self.database.get_rules(pid),
                "resources":self.database.get_resources(pid),"states":self.database.get_states(pid),
                "rag":self.database.list_rag_cases(pid,active_only=False)}

    def record_approval(self,run_id,decision,reason,actor="user"):
        approval_id=str(uuid.uuid4())
        self.database.execute("INSERT INTO approvals(approval_id,run_id,approval_type,actor,decision,reason) VALUES(?,?,?,?,?,?)",
                              (approval_id,run_id,"manual",actor,decision,reason))
        self.database.connection.commit(); self.database.update_run_status(run_id,decision.lower())
        return {"approval_id":approval_id,"run_id":run_id,"decision":decision}

    def baseline_folder(self,folder,variant=None):
        report=self.evaluate_folder(folder)
        return report["ablations"] if variant is None else report["ablations"][variant]

    def batch_folders(self,folders,request=None):
        results=[]
        for folder in folders:
            try:
                value=(self.adapt_folder(folder,request).to_dict() if request else self.report_folder(folder))
                results.append({"folder":str(folder),"status":"PASS","result":value})
            except Exception as exc:
                results.append({"folder":str(folder),"status":"FAIL","error":str(exc)})
        return {"total":len(results),"passed":sum(x["status"]=="PASS" for x in results),"results":results}

    def export_run(self,run_id,destination):
        source=self.settings.output_root/run_id
        if not source.is_dir(): raise ValueError(f"Run artefacts not found: {run_id}")
        files=sorted(path for path in source.rglob("*") if path.is_file())
        manifest={str(path.relative_to(source)):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        destination=Path(destination); destination.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(destination,"w",zipfile.ZIP_DEFLATED) as archive:
            for path in files: archive.write(path,str(path.relative_to(source)))
            archive.writestr("export_manifest.json",json.dumps({"run_id":run_id,"files":manifest},sort_keys=True,indent=2))
        return destination

    def replay_run(self,run_id):
        candidate=Path(run_id)
        if candidate.is_file() and zipfile.is_zipfile(candidate):
            with zipfile.ZipFile(candidate,"r") as archive:
                manifest=json.loads(archive.read("export_manifest.json"))
                for name,digest in manifest["files"].items():
                    if hashlib.sha256(archive.read(name)).hexdigest()!=digest:
                        raise ValueError(f"Replay checksum mismatch: {name}")
                payload=json.loads(archive.read("result.json"))
            request=payload["decision"]["request"]
            return self.adapt_folder(request["source_folder"],request["raw_text"],
                                     target=request["target_element"],operation=request["operation"])
        path=self.settings.output_root/run_id/"result.json"
        if not path.is_file(): raise ValueError(f"Replay source not found: {run_id}")
        payload=json.loads(path.read_text(encoding="utf-8")); request=payload["decision"]["request"]
        return self.adapt_folder(request["source_folder"],request["raw_text"],
                                 target=request["target_element"],operation=request["operation"])

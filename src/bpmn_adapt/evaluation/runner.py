"""Multi-layer ground truth and RAG-ablation evaluation."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import uuid

from bpmn_adapt.simulation.engine import simulate
from bpmn_adapt.agents.analyst import AnalystAgent
from bpmn_adapt.domain.models import DecisionStatus
from bpmn_adapt.evaluation.evidence import EvidenceWriter
from bpmn_adapt.evaluation.statistics import StatisticalAnalyzer


LAYERS=("request_decision","constraint_reasoning","structural_adaptation","token_migration","executability","rag_usefulness")


def _field(record,*names):
    for name in names:
        if name in record and record[name]: return record[name]
    return ""


class EvaluationRunner:
    def __init__(self,application): self.application=application

    def evaluate(self,folder):
        bundle=self.application.ingest(folder); process_id=bundle.definition.process_id
        cases=[]
        for record in bundle.test_cases:
            expected=_field(record,"expected_result","validation_status").upper()
            action=_field(record,"user_request_/_process_action","user_request_or_process_action","user_request","process_action")
            target=action
            for prefix in ("Execute or validate ","Execute ","Validate "):
                if target.casefold().startswith(prefix.casefold()): target=target[len(prefix):]
            target=target.rstrip(". ")
            cases.append({"case_id":record.get("id","unknown"),"expected":expected,"action":action,"target":target,"has_oracle":bool(expected)})
        run_id=f"evaluation-{uuid.uuid4()}"; self.application.database.create_run(run_id,process_id,self.application.settings.fingerprint(),"evaluation")
        queries=[case["action"] for case in cases if case["action"]]
        ablations={}
        variant_modes=(("conversational","none"),("no_simulation","hybrid"),
                       ("none","none"),("syntactic","syntactic"),
                       ("semantic","semantic"),("hybrid","hybrid"),
                       ("hybrid_after_updates","hybrid"))
        observations=[]
        for variant,mode in variant_modes:
            hits=0; total=0; correct=0; constraint_correct=0; predictions=[]
            previous=self.application.rag.default_mode; self.application.rag.default_mode=mode
            try:
                analyst=AnalystAgent(self.application.database,self.application.rag,self.application.llm)
                for case in cases:
                    if not case["action"]: continue
                    if not case["expected"]:
                        observations.append({"scenario_id":case["case_id"],"variant":variant,
                                             "status":"NOT_EVALUABLE","reason":"missing ground truth"})
                        continue
                    request=self.application._request(bundle,case["action"],target=case["target"],operation="REMOVE")
                    decision=analyst.analyse(request,run_id=run_id)
                    # Conversational baseline intentionally bypasses the DB-authoritative
                    # rule decision while retaining identical inputs and manifest.
                    predicted=("PASS" if variant=="conversational" else
                               "BLOCKED" if decision.status==DecisionStatus.REJECT else "PASS")
                    expected="BLOCKED" if case["expected"] in {"BLOCKED","REJECT","FAIL"} else "PASS"
                    is_correct=predicted==expected; correct+=int(is_correct); total+=1; hits+=int(bool(decision.evidence_ids))
                    expects_rule="RULE" in case["case_id"]; expects_resource="RESOURCE" in case["case_id"]
                    reasoning_ok=(bool(decision.rule_ids)==expects_rule and bool(decision.resource_ids)==expects_resource) if (expects_rule or expects_resource) else not decision.rule_ids and not decision.resource_ids
                    constraint_correct+=int(reasoning_ok)
                    predictions.append({"case_id":case["case_id"],"expected":expected,"predicted":predicted,"correct":is_correct,"rule_ids":list(decision.rule_ids),"resource_ids":list(decision.resource_ids),"evidence_ids":list(decision.evidence_ids)})
                    observations.append({"scenario_id":case["case_id"],"variant":variant,
                                         "expected":expected,"predicted":predicted,
                                         "correct":is_correct,"evidence_ids":list(decision.evidence_ids),
                                         "status":"EVALUATED" if case["expected"] else "NOT_EVALUABLE"})
            finally: self.application.rag.default_mode=previous
            ablations[variant]={"queries":total,"retrieval_coverage":(hits/total if total else None),"decision_accuracy":(correct/total if total else None),"constraint_reasoning_accuracy":(constraint_correct/total if total else None),"predictions":predictions}
        traces,failures=simulate(bundle.bpmn_xml)
        layers={
            "request_decision":{"oracle_cases":sum(bool(c["expected"]) for c in cases),"accuracy":ablations["hybrid"]["decision_accuracy"]},
            "constraint_reasoning":{"oracle_cases":len(cases),"accuracy":ablations["hybrid"]["constraint_reasoning_accuracy"]},
            "structural_adaptation":{"oracle":"original BPMN for remove/re-add","status":"NOT_EVALUABLE without an adaptation output; MetricSuite computes labeled GED when present"},
            "token_migration":{"states":len(bundle.definition.states),"status":"NOT_EVALUABLE without expected token mappings"},
            "executability":{"source_model_passed":not failures,"trace_count":len(traces)},
            "rag_usefulness":{"modes":["none","syntactic","semantic","hybrid","hybrid_after_updates"],"measured_by":"compatible evidence supporting correct decisions"},
        }
        output=self.application.settings.output_root/run_id; output.mkdir(parents=True,exist_ok=True)
        payload={"evaluation_id":run_id,"process_id":process_id,"folder":str(Path(folder).resolve()),"ground_truth_layers":layers,"ablations":ablations,"cases":cases,"config_fingerprint":self.application.settings.fingerprint()}
        report_path=output/"evaluation.json"; report_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        with (output/"ablation_summary.csv").open("w",newline="",encoding="utf-8") as handle:
            writer=csv.writer(handle); writer.writerow(("mode","queries","retrieval_coverage","decision_accuracy","constraint_reasoning_accuracy"))
            for mode,data in ablations.items(): writer.writerow((mode,data["queries"],data["retrieval_coverage"],data["decision_accuracy"],data["constraint_reasoning_accuracy"]))
        paired_hybrid=[int(row["correct"]) for row in observations if row["variant"]=="hybrid"]
        paired_no_rag=[int(row["correct"]) for row in observations if row["variant"]=="none"]
        statistics={}
        if paired_hybrid and len(paired_hybrid)==len(paired_no_rag):
            result=StatisticalAnalyzer(seed=self.application.settings.evaluation_seed).compare_binary(
                paired_no_rag,paired_hybrid)
            statistics["hybrid_vs_no_rag"]={key:(value.value if hasattr(value,"value") else value)
                                               for key,value in result.__dict__.items()}
        EvidenceWriter().write(output,observations,statistics,{"evaluation_id":run_id,
            "process_id":process_id,"config_fingerprint":self.application.settings.fingerprint(),
            "variants":[name for name,_ in variant_modes]})
        payload["report_path"]=str(report_path); self.application.database.update_run_status(run_id,"evaluation_complete")
        return payload

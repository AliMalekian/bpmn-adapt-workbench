"""Multi-layer thesis metrics with explicit evaluability and denominators."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import xml.etree.ElementTree as ET


class EvaluationStatus(str,Enum): EVALUATED="EVALUATED"; NOT_EVALUABLE="NOT_EVALUABLE"


@dataclass(frozen=True)
class Observation:
    scenario_id:str; variant:str; decision:str
    bpmn_xml:str|None=None; token_mappings:dict[str,str]=field(default_factory=dict)
    variable_mappings:dict[str,str]=field(default_factory=dict)
    expected_tokens:tuple[str,...]=(); constraint_ids:tuple[str,...]=()
    retrieved_ids:tuple[str,...]=(); schema_pass:bool|None=None
    semantic_pass:bool|None=None; formal_pass:bool|None=None; engine_pass:bool|None=None
    deadlock_recovered:bool|None=None; latency_seconds:float|None=None
    llm_tokens:int|None=None; monetary_cost:float|None=None


@dataclass(frozen=True)
class GroundTruth:
    expected_decision:str|None=None; oracle_bpmn_xml:str|None=None
    expected_tokens:tuple[str,...]=(); expected_variables:tuple[str,...]=()
    expected_constraints:tuple[str,...]=(); relevant_evidence:tuple[str,...]=()
    contradictory:bool=False


@dataclass(frozen=True)
class MetricRecord:
    scenario_id:str; variant:str; status:EvaluationStatus
    metrics:dict[str,float|bool|None]; denominator:int; reason:str|None=None


class MetricSuite:
    def evaluate(self,observation:Observation,truth:GroundTruth):
        if truth.contradictory:
            return MetricRecord(observation.scenario_id,observation.variant,
                                EvaluationStatus.NOT_EVALUABLE,{},0,"contradictory ground truth")
        if not any((truth.expected_decision,truth.oracle_bpmn_xml,truth.expected_tokens,
                    truth.expected_variables,truth.expected_constraints,truth.relevant_evidence)):
            return MetricRecord(observation.scenario_id,observation.variant,
                                EvaluationStatus.NOT_EVALUABLE,{},0,"missing ground truth")
        metrics:dict[str,Any]={}
        if truth.expected_decision is not None:
            metrics["decision_correct"]=observation.decision==truth.expected_decision
        if truth.oracle_bpmn_xml and observation.bpmn_xml:
            distance,total=_graph_distance(truth.oracle_bpmn_xml,observation.bpmn_xml)
            metrics["graph_edit_distance"]=float(distance)
            metrics["restoration_similarity"]=max(0.0,1-distance/max(1,total))
        expected_tokens=truth.expected_tokens or observation.expected_tokens
        if expected_tokens:
            output_nodes=_nodes(observation.bpmn_xml)[0] if observation.bpmn_xml else {}
            preserved=sum(1 for token in expected_tokens
                          if observation.token_mappings.get(token,token) in output_nodes)
            metrics["token_preservation"]=preserved/len(expected_tokens)
        if truth.expected_variables:
            metrics["variable_preservation"]=sum(
                observation.variable_mappings.get(key,key) in truth.expected_variables
                for key in truth.expected_variables)/len(truth.expected_variables)
        if truth.expected_constraints:
            metrics["constraint_recall"]=len(set(truth.expected_constraints)&set(observation.constraint_ids))/len(truth.expected_constraints)
        if truth.relevant_evidence:
            metrics["retrieval_recall"]=len(set(truth.relevant_evidence)&set(observation.retrieved_ids))/len(truth.relevant_evidence)
        for name in ("schema_pass","semantic_pass","formal_pass","engine_pass",
                     "deadlock_recovered","latency_seconds","llm_tokens","monetary_cost"):
            value=getattr(observation,name)
            if value is not None: metrics[name]=value
        return MetricRecord(observation.scenario_id,observation.variant,
                            EvaluationStatus.EVALUATED,metrics,1)


def _nodes(xml):
    if not xml:return {},set()
    root=ET.fromstring(xml); nodes={}; edges=set()
    for item in root.iter():
        kind=item.tag.rsplit("}",1)[-1]; identifier=item.get("id")
        if kind=="sequenceFlow" and item.get("sourceRef") and item.get("targetRef"):
            edges.add((item.get("sourceRef"),item.get("targetRef"),item.get("name","")))
        elif identifier and kind not in {"definitions","process","BPMNDiagram","BPMNPlane","BPMNShape","BPMNEdge","Bounds"}:
            nodes[identifier]=(kind,item.get("name",""))
    return nodes,edges


def _graph_distance(left,right):
    ln,le=_nodes(left); rn,re=_nodes(right)
    common=set(ln)&set(rn)
    distance=len(set(ln)^set(rn))+sum(ln[key]!=rn[key] for key in common)+len(le^re)
    return distance,max(len(ln)+len(le),len(rn)+len(re))

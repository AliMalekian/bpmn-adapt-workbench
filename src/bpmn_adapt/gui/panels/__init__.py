"""Dedicated inspection-panel renderers."""
import json

def raw(payload): return json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)
def _section(title,payload,fields):
    lines=[title,""]
    for field in fields:
        if field in payload: lines.append(f"{field}: {json.dumps(payload[field],ensure_ascii=False,sort_keys=True)}")
    return "\n".join(lines)+"\n\nRaw JSON\n"+raw(payload)
def render_project(payload): return _section("Project and dataset",payload,("process_id","name","folder","status"))
def render_facts(payload): return _section("Authoritative DB facts",payload,("process","rules","resources","states"))
def render_rag(payload): return _section("RAG ranking and component scores",payload,("filters","hits","rag","scores","ranking"))
def render_planning(payload): return _section("Temporal plan and cost alternatives",payload,("status","selected_plan","pareto_plans","diagnostics"))
def render_model(payload): return _section("Structural diff and token migration",payload,("candidate","diff","migration","inverse_operations"))
def render_traces(payload):
    lines=["Simulation traces and failures"]
    for trace in payload.get("traces",[]): lines.append(" → ".join(trace))
    return "\n".join(lines)+"\n\nRaw JSON\n"+raw(payload)
def render_evaluation(payload): return _section("Evaluation metrics and statistics",payload,("ablations","metrics","statistics","artifacts"))
def render_provenance(payload): return _section("Audit provenance and approval",payload,("run_id","status","approval","events","configuration_fingerprint"))
def render_export(payload): return _section("Export and replay checksums",payload,("archive","checksums","replay","status"))

from .base import InspectionPanel
__all__=["InspectionPanel","render_project","render_facts","render_rag","render_planning",
         "render_model","render_traces","render_evaluation","render_provenance","render_export"]

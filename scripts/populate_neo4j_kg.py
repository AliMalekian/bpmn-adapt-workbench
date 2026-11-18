"""
ETL Ingestion Script: Comprehensive Ingestion of all 82 BPMN Processes into Neo4j Knowledge Graph.

Populates:
1. Process Nodes (SHA-256 process_id, folder_name, name, domain, cluster)
2. Tasks & Gateways (extracted via BpmnGraph from XML)
3. Sequence Flows (connecting Tasks, Gateways, Events)
4. Business Rules & GOVERNED_BY Relationships (binding tasks to normative rules)
5. Resource Roles & HAS_RESOURCE Relationships (capacities, human roles, metrics)
6. Decision Precedents & HAS_PRECEDENT Relationships (historical approved/rejected adaptation cases)
"""

from __future__ import annotations
import logging
import os
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from bpmn_adapt.bpmn.graph import BpmnGraph
from bpmn_adapt.ingestion.discovery import ingest_folder
from bpmn_adapt.retrieval.knowledge_graph import BPMNKnowledgeGraphService

import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("neo4j_full_etl")


def classify_rule(text: str) -> tuple[str, str]:
    t = text.lower().strip()
    cond_patterns = [r'\bif\b', r'\bwhen\b', r'\bunless\b', r'\bin case\b', r'\bwhere\b', r'\bonly if\b', r'\boptional\b', r'\bmay\b', r'\bcan\b']
    if any(re.search(p, t) for p in cond_patterns):
        return 'CONDITIONAL', 'CONDITIONAL'
    metric_patterns = [r'\bmaximum\b', r'\bminimum\b', r'\bat least\b', r'\bat most\b', r'\bcapacity\b', r'\bbetween \d+\b', r'\bfee\b', r'\brate\b', r'\bper shift\b', r'\bper month\b', r'\bseconds\b', r'\bminutes\b', r'\bdays\b', r'%']
    if any(re.search(p, t) for p in metric_patterns):
        return 'METRIC_THRESHOLD', 'METRIC'
    mandate_patterns = [r'\bmust\b', r'\bshall\b', r'\brequired\b', r'\bmandatory\b', r'\bprohibited\b', r'\bnever\b', r'\bforbidden\b']
    if any(re.search(p, t) for p in mandate_patterns):
        return 'INVARIANT_MANDATE', 'MANDATORY'
    return 'DESCRIPTIVE_POLICY', 'DESCRIPTIVE'


def run_full_etl(neo4j_uri="bolt://127.0.0.1:7687", auth=("neo4j", "123456789")):
    dataset_dir = project_root / "dataset"
    if not dataset_dir.exists():
        dataset_dir = Path("E:/Implemention_dataset enriched")

    logger.info("Initializing Neo4j Knowledge Graph Service at %s...", neo4j_uri)
    kg = BPMNKnowledgeGraphService(uri=neo4j_uri, auth=auth)
    if not kg.connect():
        raise RuntimeError(f"Could not connect to Neo4j at {neo4j_uri}")

    logger.info("Setting up schema constraints and indexes...")
    kg.initialize_schema()

    process_dirs = sorted([d for d in dataset_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
    logger.info("Discovered %d process datasets to ingest.", len(process_dirs))

    total_tasks = 0
    total_gateways = 0
    total_flows = 0
    total_rules = 0
    total_resources = 0
    total_precedents = 0

    with kg._driver.session(database=kg.database) as session:
        for idx, pdir in enumerate(process_dirs, 1):
            fname = pdir.name
            try:
                bundle = ingest_folder(pdir)
            except Exception as e:
                logger.warning("Could not ingest folder %s: %s", fname, e)
                continue

            pid = bundle.definition.process_id
            name = bundle.definition.name
            cluster = "Pmo" if "pmo" in fname.lower() else ("Mangler" if "mangler" in fname.lower() else "Camunda")
            domain = "Banking/Finance" if any(w in fname.lower() for w in ("credit", "scoring", "audit")) else "General Business"

            # Parse BPMN Graph
            graph = BpmnGraph.from_xml(bundle.bpmn_xml)

            tasks = []
            gateways = []
            flows = []

            for n in graph.nodes.values():
                k_low = n.kind.lower()
                clean_name = n.name.strip() if n.name else n.element_id
                if "task" in k_low:
                    tasks.append({"id": n.element_id, "name": clean_name, "type": n.kind})
                elif "gateway" in k_low:
                    gateways.append({"id": n.element_id, "name": clean_name, "type": n.kind})

            for f in graph.flows.values():
                flows.append({
                    "id": f.element_id,
                    "source_ref": f.source_ref,
                    "target_ref": f.target_ref,
                })

            # Rules and Governed Elements
            rules = []
            for r in bundle.definition.rules:
                r_text_low = r.text.lower()
                gov_elems = []
                for t in tasks:
                    t_name = t["name"]
                    if len(t_name) > 3 and (t_name.lower() in r_text_low or any(w in r_text_low for w in t_name.lower().split() if len(w) > 4)):
                        gov_elems.append(t_name)
                rtype, strictness = classify_rule(r.text)
                rules.append({
                    "rule_id": r.rule_id,
                    "text": r.text,
                    "governed_elements": gov_elems,
                    "category": "REGULATORY_COMPLIANCE",
                    "rule_type": rtype,
                    "strictness": strictness,
                })

            # Resources
            resources = []
            for res in bundle.definition.resources:
                resources.append({
                    "name": res.name,
                    "capacity": str(res.value),
                    "type": "RESOURCE_SPEC",
                })

            # Ingest Topology into Neo4j
            kg.ingest_process_topology(
                process_id=pid,
                name=name,
                domain=domain,
                cluster=cluster,
                tasks=tasks,
                gateways=gateways,
                flows=flows,
                rules=rules,
                resources=resources,
                folder_name=fname,
            )

            # Ingest Historical Decision Precedents from RagData.txt
            prec_count = 0
            for prec_idx, rec in enumerate(bundle.rag_records, 1):
                case_id = f"prec-{fname}-{rec.get('id', prec_idx)}"
                op = rec.get("operation_type", "REMOVE").replace("RE_ADD", "RE_ADD")
                dec = rec.get("decision", "UNKNOWN")
                target = rec.get("target_bpmn_element", "") or rec.get("target", "")
                reason = rec.get("decision_reason", "") or rec.get("reason", "")
                rules_cited = rec.get("referenced_rules", "")

                session.run(
                    """
                    MERGE (dp:DecisionPrecedent {case_id: $cid})
                    ON CREATE SET dp.decision = $dec,
                                  dp.process_id = $pid,
                                  dp.folder_name = $fname,
                                  dp.target_element_name = $target,
                                  dp.operation = $op,
                                  dp.reason = $reason,
                                  dp.referenced_rules = $rules_cited
                    ON MATCH SET dp.decision = $dec,
                                 dp.process_id = $pid,
                                 dp.folder_name = $fname,
                                 dp.target_element_name = $target,
                                 dp.operation = $op,
                                 dp.reason = $reason,
                                 dp.referenced_rules = $rules_cited
                    WITH dp
                    MATCH (p:Process {process_id: $pid})
                    MERGE (p)-[:HAS_PRECEDENT]->(dp)
                    """,
                    cid=case_id,
                    dec=dec,
                    pid=pid,
                    fname=fname,
                    target=target,
                    op=op,
                    reason=reason,
                    rules_cited=rules_cited,
                )

                if target:
                    session.run(
                        """
                        MATCH (t:Task {process_id: $pid})
                        WHERE toLower(t.name) CONTAINS toLower($tgt) OR toLower($tgt) CONTAINS toLower(t.name)
                        MATCH (dp:DecisionPrecedent {case_id: $cid})
                        MERGE (dp)-[:TARGETS_TASK]->(t)
                        """,
                        pid=pid,
                        tgt=target,
                        cid=case_id,
                    )

                prec_count += 1

            total_tasks += len(tasks)
            total_gateways += len(gateways)
            total_flows += len(flows)
            total_rules += len(rules)
            total_resources += len(resources)
            total_precedents += prec_count

            if idx % 10 == 0 or idx == len(process_dirs):
                logger.info(
                    "[%d/%d] Ingested '%s' -> Tasks: %d, Gateways: %d, Flows: %d, Rules: %d, Resources: %d, Precedents: %d",
                    idx, len(process_dirs), fname, len(tasks), len(gateways), len(flows), len(rules), len(resources), prec_count
                )

    kg.close()
    logger.info("=" * 60)
    logger.info("🎉 FULL NEO4J KNOWLEDGE GRAPH INGESTION COMPLETE!")
    logger.info("Total Processes Ingested: %d", len(process_dirs))
    logger.info("Total Tasks:             %d", total_tasks)
    logger.info("Total Gateways:          %d", total_gateways)
    logger.info("Total Sequence Flows:    %d", total_flows)
    logger.info("Total Business Rules:    %d", total_rules)
    logger.info("Total Resources:         %d", total_resources)
    logger.info("Total Precedents:        %d", total_precedents)
    logger.info("=" * 60)


if __name__ == "__main__":
    run_full_etl()

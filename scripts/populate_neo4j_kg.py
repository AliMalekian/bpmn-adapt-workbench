"""
ETL Ingestion Script: Populate Clean Neo4j Heterogeneous Knowledge Graph from 82 BPMN Datasets.
"""

import os
import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path
import logging

# Ensure src is on path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from bpmn_adapt.retrieval.knowledge_graph import BPMNKnowledgeGraphService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("neo4j_etl")


def parse_bpmn_xml(bpmn_path: Path):
    tasks = []
    gateways = []
    flows = []

    if not bpmn_path.exists():
        return tasks, gateways, flows

    try:
        tree = ET.parse(bpmn_path)
        root = tree.getroot()
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            elem_id = elem.attrib.get("id", "")
            elem_name = elem.attrib.get("name", elem_id)

            if "task" in tag.lower():
                tasks.append({"id": elem_id, "name": elem_name.strip(), "type": tag})
            elif "gateway" in tag.lower():
                gateways.append({"id": elem_id, "name": elem_name.strip(), "type": tag})
            elif tag == "sequenceFlow":
                flows.append({
                    "id": elem_id,
                    "source_ref": elem.attrib.get("sourceRef", ""),
                    "target_ref": elem.attrib.get("targetRef", "")
                })
    except Exception as e:
        logger.warning("Error parsing BPMN at %s: %s", bpmn_path, e)

    return tasks, gateways, flows


def parse_rules_file(rules_path: Path):
    rules = []
    if not rules_path.exists():
        return rules

    content = rules_path.read_text(encoding="utf-8-sig", errors="ignore")
    lines = content.splitlines()
    cur_rule = None

    for line in lines:
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue

        # Match: 1. Rule text, Rule 1: text, R1: text
        m = re.match(r"^(\d+\.|\bRule\s*\d+:?|\bR\d+:?)\s*(.*)", line_str, re.IGNORECASE)
        if m:
            prefix = m.group(1).rstrip(":.").strip()
            rid = f"R{prefix}" if prefix.isdigit() else prefix
            text = m.group(2).strip()
            cur_rule = {
                "rule_id": rid,
                "text": text,
                "governed_elements": [],
                "category": "REGULATORY_COMPLIANCE"
            }
            rules.append(cur_rule)
        elif cur_rule:
            cur_rule["text"] += " " + line_str

    return rules


def parse_resources_file(resources_path: Path):
    resources = []
    if not resources_path.exists():
        return resources

    content = resources_path.read_text(encoding="utf-8-sig", errors="ignore")
    for line in content.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue
        parts = line_str.split(":", 1)
        name = parts[0].strip()
        cap = parts[1].strip() if len(parts) > 1 else ""
        resources.append({"name": name, "capacity": cap, "type": "HUMAN_ROLE"})

    return resources


def run_etl(neo4j_uri="bolt://localhost:7687", auth=("neo4j", "123456789")):
    dataset_dir = project_root / "dataset"
    if not dataset_dir.exists():
        logger.error("Dataset directory not found at %s", dataset_dir)
        return

    kg = BPMNKnowledgeGraphService(uri=neo4j_uri, auth=auth)
    logger.info("Attempting connection to Neo4j at %s...", neo4j_uri)
    if not kg.connect():
        logger.error("Could not connect to Neo4j.")
        return

    kg.initialize_schema()

    process_dirs = sorted([d for d in dataset_dir.iterdir() if d.is_dir()])
    logger.info("Found %d process datasets to ingest.", len(process_dirs))

    ingested = 0
    total_rules_count = 0
    total_tasks_count = 0

    for pdir in process_dirs:
        pid = pdir.name
        cluster = "Pmo" if "pmo" in pid.lower() else ("Mangler" if "mangler" in pid.lower() else "Camunda")
        domain = "Banking/Finance" if "credit" in pid.lower() or "scoring" in pid.lower() else "General Business"

        # BPMN file discovery
        bpmn_file = pdir / "model.bpmn"
        if not bpmn_file.exists():
            xmls = list(pdir.glob("*.bpmn"))
            if xmls:
                bpmn_file = xmls[0]

        tasks, gateways, flows = parse_bpmn_xml(bpmn_file)

        # Rules discovery
        rules_file = pdir / "Business_Rules.txt"
        if not rules_file.exists():
            rules_file = pdir / "Rules.txt"
        rules = parse_rules_file(rules_file)

        # Auto-detect governed elements for each rule based on task mentions
        for r in rules:
            r_text_low = r["text"].lower()
            for t in tasks:
                t_name = t.get("name", "").strip()
                if len(t_name) > 3 and (t_name.lower() in r_text_low or any(w in r_text_low for w in t_name.lower().split() if len(w) > 4)):
                    r["governed_elements"].append(t_name)

        # Resources discovery
        res_file = pdir / "Resources.txt"
        resources = parse_resources_file(res_file)

        kg.ingest_process_topology(
            process_id=pid,
            name=pid,
            domain=domain,
            cluster=cluster,
            tasks=tasks,
            gateways=gateways,
            flows=flows,
            rules=rules,
            resources=resources,
        )

        total_rules_count += len(rules)
        total_tasks_count += len(tasks)
        ingested += 1

        if ingested % 10 == 0 or ingested == len(process_dirs):
            logger.info(
                "Ingested %d / %d processes (Total Tasks: %d, Total Rules: %d).",
                ingested, len(process_dirs), total_tasks_count, total_rules_count
            )

    kg.close()
    logger.info("Knowledge Graph ETL completed successfully.")


if __name__ == "__main__":
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pwd = os.environ.get("NEO4J_PASSWORD", "123456789")
    run_etl(neo4j_uri=uri, auth=(user, pwd))

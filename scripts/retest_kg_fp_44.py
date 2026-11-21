"""
Targeted Re-Evaluation of the 44 Knowledge Graph False Positive Scenarios.
Evaluates the 44 previous FP scenarios using:
1. Two-Axis Knowledge Graph (Pure KG: enable_kg=True, enable_rag=False)
2. Hybrid Two-Axis Graph-RAG (enable_kg=True, enable_rag=True)

Verifies elimination of False Positives through strict obligation enforcement.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import sys
import time

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.ingestion.discovery import ingest_folder
from bpmn_adapt.domain.models import AdaptationRequest, OperationType
from bpmn_adapt.providers.manager import ProviderManager
from bpmn_adapt.retrieval.knowledge_graph import BPMNKnowledgeGraphService

logging.basicConfig(level=logging.WARNING)


def load_fp_cases() -> list[dict]:
    tests_file = project_root / "experiments" / "master_full_82_kg_pure" / "tests.jsonl"
    fps = []
    with open(tests_file, "r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            gt = (d.get("ground_truth_decision") or "").upper()
            pred = (d.get("decision") or "").upper()
            if pred == "APPROVE" and gt == "REJECT":
                fps.append(d)
    return fps


def run_targeted_eval(mode: str = "kg_pure", max_cases: int = 44):
    enable_kg = True
    enable_rag = (mode == "graph_rag")

    print("\n" + "=" * 78, flush=True)
    print(f"🎯 TARGETED DIAGNOSTIC EVALUATION ({mode.upper()}) ON 44 PREVIOUS FP CASES", flush=True)
    print(f"KG={enable_kg} | RAG={enable_rag} | Two-Axis Ontology + Strict Invariance Prompt", flush=True)
    print("=" * 78 + "\n", flush=True)

    fp_cases = load_fp_cases()
    if max_cases:
        fp_cases = fp_cases[:max_cases]
    print(f"Loaded {len(fp_cases)} False Positive scenarios to evaluate.\n", flush=True)

    # 1. Check Neo4j
    kg = BPMNKnowledgeGraphService()
    if not kg.connect():
        raise RuntimeError("Could not connect to Neo4j. Is the container running?")
    print("Neo4j Knowledge Graph connected.", flush=True)

    # 2. Check Provider
    mgr = ProviderManager(project_root / "providers.json")
    um_test = mgr.test("um-llm1-gemma4")
    print(f"UM LLM1 Provider Status: {um_test.get('status')} | Latency: {um_test.get('latency')}s\n", flush=True)
    if um_test.get("status") != "OK":
        raise RuntimeError(f"UM LLM1 is offline: {um_test.get('error')}")

    p_client = mgr.build_client("um-llm1-gemma4")
    settings = Settings.load(overrides={"llm_mode": "live", "embedding_provider": "hash_test"})
    app = RuntimeAdaptationApplication.from_settings(settings)
    app.llm = p_client
    app.orchestrator.llm = p_client
    app.orchestrator.analyst.llm = p_client
    app.orchestrator.analyst.enable_rag = enable_rag
    app.orchestrator.analyst.enable_kg = enable_kg
    app.orchestrator.analyst.kg = kg
    app.orchestrator.modeler.llm = p_client
    app.orchestrator.experimenter.llm = p_client

    dataset_root = project_root / "dataset"
    if not dataset_root.exists():
        dataset_root = Path("E:/Implemention_dataset enriched")

    # Group scenarios by dataset
    by_dataset: dict[str, list[dict]] = {}
    for c in fp_cases:
        ds = c.get("dataset")
        by_dataset.setdefault(ds, []).append(c)

    results = []
    total_evaluated = 0
    total_rejected = 0  # GT is REJECT, so REJECT = SUCCESS (FP eliminated)

    for ds_name, cases in by_dataset.items():
        ds_dir = dataset_root / ds_name
        if not ds_dir.exists():
            print(f"Skipping {ds_name} (directory not found)", flush=True)
            continue

        for case in cases:
            tid = case["test_id"]
            op_str = case.get("operation", "REMOVE")
            target = case.get("target", "")

            t0 = time.time()
            try:
                res = app.adapt_folder(
                    ds_dir,
                    f"{op_str} \"{target}\"",
                    target=target,
                    operation=op_str,
                )
                lat = time.time() - t0
                new_dec = res.decision.status.value.upper()
                new_reason = res.decision.reason
            except Exception as e:
                lat = time.time() - t0
                new_dec = "ERROR"
                new_reason = str(e)

            is_eliminated = (new_dec == "REJECT")
            total_evaluated += 1
            if is_eliminated:
                total_rejected += 1

            status_symbol = "✅ ELIMINATED (Now REJECT)" if is_eliminated else "❌ STILL FP (Approved)"
            print(f"[{total_evaluated:02d}/{len(fp_cases):02d}] {tid} -> {status_symbol} ({lat:.1f}s)", flush=True)
            print(f"   Reason: {new_reason[:150]}...", flush=True)

            results.append({
                "test_id": tid,
                "dataset": ds_name,
                "target": target,
                "operation": op_str,
                "ground_truth": "REJECT",
                "old_prediction": "APPROVE",
                "new_prediction": new_dec,
                "fp_eliminated": is_eliminated,
                "reason": new_reason,
                "latency_s": round(lat, 2),
            })

    kg.close()

    elimination_rate = (total_rejected / total_evaluated * 100) if total_evaluated else 0
    print("\n" + "=" * 78, flush=True)
    print(f"📊 DIAGNOSTIC RESULTS ({mode.upper()}):", flush=True)
    print(f"Evaluated: {total_evaluated} | FP Eliminated: {total_rejected} / {total_evaluated} ({elimination_rate:.2f}%)", flush=True)
    print("=" * 78 + "\n", flush=True)

    out_file = project_root / "experiments" / f"diagnostic_{mode}_fp_results.json"
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["kg_pure", "graph_rag"], default="kg_pure")
    parser.add_argument("--max", type=int, default=44)
    args = parser.parse_args()
    run_targeted_eval(mode=args.mode, max_cases=args.max)

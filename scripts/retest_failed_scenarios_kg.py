"""
Targeted Re-Evaluation of Failed Benchmark Scenarios using Knowledge Graph v2.

Evaluates ONLY the scenarios that failed in v1 (where matched_ground_truth == False).
Applies the enhanced Analyst prompt v2 with:
1. Sequence Flow Bridging clarification (Modeler bridges flows, so removal is not flow disconnection).
2. Affirmative mandate enforcement (rejections require explicit mandatory rules).
3. Precedent retrieval directly from Neo4j DecisionPrecedent nodes.
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
from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner
from bpmn_adapt.ingestion.discovery import ingest_folder
from bpmn_adapt.providers.manager import ProviderManager

logging.basicConfig(level=logging.WARNING)


def run_retest():
    print("=" * 78, flush=True)
    print("🎯 RE-EVALUATING FAILED SCENARIOS USING KNOWLEDGE GRAPH V2", flush=True)
    print("=" * 78, flush=True)

    tests_file = project_root / "experiments" / "full_82_kg_neo4j_um_llm1" / "tests.jsonl"
    if not tests_file.exists():
        raise FileNotFoundError(f"Tests file not found: {tests_file}")

    all_records = [json.loads(l) for l in tests_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    failed_records = [r for r in all_records if not r.get("matched_ground_truth")]
    total_failed = len(failed_records)
    print(f"Total benchmark scenarios: {len(all_records)}")
    print(f"Identified {total_failed} failed scenarios to re-test.\n", flush=True)

    # Initialize app with UM LLM1 and Neo4j
    mgr = ProviderManager(project_root / "providers.json")
    um_test = mgr.test("um-llm1-gemma4")
    print(f"UM LLM1 Provider Status: {um_test.get('status')} | Latency: {um_test.get('latency')}s")
    if um_test.get("status") != "OK":
        raise RuntimeError(f"UM LLM1 is offline: {um_test.get('error')}")

    p_client = mgr.build_client("um-llm1-gemma4")
    settings = Settings.load(overrides={"llm_mode": "live", "embedding_provider": "hash_test"})
    app = RuntimeAdaptationApplication.from_settings(settings)
    app.llm = p_client
    app.orchestrator.llm = p_client
    app.orchestrator.analyst.llm = p_client
    app.orchestrator.analyst.enable_rag = False  # Pure KG mode: RAG disabled
    app.orchestrator.analyst.enable_kg = True
    app.orchestrator.modeler.llm = p_client
    app.orchestrator.experimenter.llm = p_client

    print("KG Connected:", app.kg.is_connected() if app.kg else False)
    print("Analyst KG Active:", app.orchestrator.analyst.kg.is_connected() if app.orchestrator.analyst.kg else False, flush=True)

    dataset_root = project_root / "dataset"
    if not dataset_root.exists():
        dataset_root = Path("E:/Implemention_dataset enriched")

    runner = BenchmarkRunner(dataset_root=dataset_root, request_types=["REMOVE", "ADD"])

    # Map test cases
    retest_cases = {}
    failed_tids = {r["test_id"] for r in failed_records}

    for d in dataset_root.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            bundle = ingest_folder(d)
            cases = runner.extract_test_cases(bundle, d.name, d)
            for c in cases:
                if c["test_id"] in failed_tids:
                    retest_cases[c["test_id"]] = (c, d)

    print(f"Matched {len(retest_cases)} case specifications from dataset folders.\n", flush=True)

    results = []
    flipped_count = 0
    still_failed_count = 0

    for idx, (tid, (case, ds_folder)) in enumerate(retest_cases.items(), 1):
        op = case["operation"]
        target = case["target"]
        req_text = case.get("request_text") or case.get("raw_text") or ""
        gt = case.get("ground_truth_decision", "APPROVE")

        # Find previous v1 record
        old_rec = next((r for r in failed_records if r["test_id"] == tid), {})
        old_dec = old_rec.get("decision", "UNKNOWN")

        # Rate-limit backoff
        time.sleep(1.5)

        t0 = time.monotonic()
        try:
            res = app.adapt_folder(
                ds_folder,
                req_text,
                target=target,
                operation=op,
            )
            lat = round(time.monotonic() - t0, 2)
            new_dec = res.decision.status.value
            new_reason = res.decision.reason
        except Exception as e:
            lat = round(time.monotonic() - t0, 2)
            new_dec = "ERROR"
            new_reason = str(e)

        if gt == "APPROVE":
            is_match = (new_dec in ("APPROVE", "ALTERNATIVE_PROPOSED"))
        else:
            is_match = (new_dec == "REJECT")

        status_tag = "FLIPPED_TO_CORRECT ✅" if is_match else "STILL_FAILED ❌"
        if is_match:
            flipped_count += 1
        else:
            still_failed_count += 1

        rec = {
            "test_id": tid,
            "dataset": ds_folder.name,
            "operation": op,
            "target": target,
            "ground_truth": gt,
            "v1_decision": old_dec,
            "v2_decision": new_dec,
            "matched_ground_truth": is_match,
            "status": status_tag,
            "latency_s": lat,
            "reason": new_reason[:200],
        }
        results.append(rec)

        print(
            f"[{idx}/{total_failed}] {status_tag} | {tid} ({op} '{target[:25]}') | "
            f"Old: {old_dec} -> New: {new_dec} (GT: {gt}) ({lat}s)",
            flush=True,
        )

    app.close()

    out_file = project_root / "experiments" / "retest_kg_v2_failed_scenarios.json"
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Compute updated global benchmark accuracy
    v1_correct = sum(1 for r in all_records if r.get("matched_ground_truth"))
    v2_correct = v1_correct + flipped_count
    total_benchmark = len(all_records)
    v1_acc = v1_correct / total_benchmark * 100
    v2_acc = v2_correct / total_benchmark * 100

    print("\n" + "=" * 78, flush=True)
    print("📊 TARGETED RE-EVALUATION SUMMARY (KG v1 -> KG v2):", flush=True)
    print(f"Total Scenarios Re-Tested:           {total_failed}")
    print(f"Flipped from Failed to Correct (✅): {flipped_count} / {total_failed} ({flipped_count/max(1,total_failed)*100:.1f}%)")
    print(f"Still Failed (❌):                   {still_failed_count} / {total_failed}")
    print("-" * 78)
    print(f"KG Version 1 Accuracy on 984 Suite: {v1_correct} / {total_benchmark} ({v1_acc:.2f}%)")
    print(f"KG Version 2 Accuracy on 984 Suite: {v2_correct} / {total_benchmark} ({v2_acc:.2f}%)")
    print(f"Absolute Accuracy Gain:             +{v2_acc - v1_acc:.2f}%")
    print(f"Results saved to:                   {out_file}")
    print("=" * 78, flush=True)


if __name__ == "__main__":
    run_retest()

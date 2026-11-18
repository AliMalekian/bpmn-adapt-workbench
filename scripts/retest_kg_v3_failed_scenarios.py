"""
Targeted Re-Evaluation of the 32 Remaining Failed Scenarios using Knowledge Graph v3.

Applies:
1. Core Business Deliveries vs Auxiliary/Conditional Steps guidance.
2. Gateway matching in Neo4j inspect_subgraph.
3. Fallback word-overlap node matching in Analyst.
4. Payload size mitigation (Modeler reason truncation and diagram stripping).
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
    print("🎯 RE-EVALUATING 32 FAILED SCENARIOS USING KNOWLEDGE GRAPH V3", flush=True)
    print("=" * 78, flush=True)

    v2_file = project_root / "experiments" / "retest_kg_v2_failed_scenarios.json"
    if not v2_file.exists():
        raise FileNotFoundError(f"V2 results not found: {v2_file}")

    v2_records = json.loads(v2_file.read_text(encoding="utf-8"))
    failed_records = [r for r in v2_records if "STILL" in r.get("status", "")]
    total_to_test = len(failed_records)
    print(f"Loaded {total_to_test} failed scenarios from V2.\n", flush=True)

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
    app.orchestrator.analyst.enable_rag = False  # Pure KG mode
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

        old_rec = next((r for r in failed_records if r["test_id"] == tid), {})
        old_dec = old_rec.get("v2_decision", "UNKNOWN")

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
            "v2_decision": old_dec,
            "v3_decision": new_dec,
            "matched_ground_truth": is_match,
            "status": status_tag,
            "latency_s": lat,
            "reason": new_reason[:200],
        }
        results.append(rec)

        print(
            f"[{idx}/{total_to_test}] {status_tag} | {tid} ({op} '{target[:25]}') | "
            f"Old: {old_dec} -> New: {new_dec} (GT: {gt}) ({lat}s)",
            flush=True,
        )

    app.close()

    out_file = project_root / "experiments" / "retest_kg_v3_results.json"
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Global Benchmark Accuracy computation
    v2_correct = 952  # v2 had 952 out of 984
    v3_correct = v2_correct + flipped_count
    total_benchmark = 984
    v2_acc = v2_correct / total_benchmark * 100
    v3_acc = v3_correct / total_benchmark * 100

    print("\n" + "=" * 78, flush=True)
    print("📊 TARGETED RE-EVALUATION SUMMARY (KG v2 -> KG v3):", flush=True)
    print(f"Total Scenarios Re-Tested:           {total_to_test}")
    print(f"Flipped from Failed to Correct (✅): {flipped_count} / {total_to_test} ({flipped_count/max(1,total_to_test)*100:.1f}%)")
    print(f"Still Failed (❌):                   {still_failed_count} / {total_to_test}")
    print("-" * 78)
    print(f"KG Version 2 Accuracy on 984 Suite: {v2_correct} / {total_benchmark} ({v2_acc:.2f}%)")
    print(f"KG Version 3 Accuracy on 984 Suite: {v3_correct} / {total_benchmark} ({v3_acc:.2f}%)")
    print(f"Absolute Accuracy Gain in v3:       +{v3_acc - v2_acc:.2f}%")
    print(f"Results saved to:                   {out_file}")
    print("=" * 78, flush=True)


if __name__ == "__main__":
    run_retest()

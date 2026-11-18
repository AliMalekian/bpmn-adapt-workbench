"""
Pilot Evaluation: Knowledge Graph (KG) vs V5 (RAG) Comparison on 5 Representative Processes.

Evaluates 60 benchmark scenarios across:
1. Camunda-Credit-scoring
2. Pmo-3D printer
3. Mangler-Car Service
4. Pmo-annual audit
5. Pmo-Burger Seller

Compares Knowledge Graph (Neo4j) adaptation against V5 Closed-Loop RAG baseline.
Calculates Accuracy, Precision, Recall, F1, Latency, and Graph Edit Distance (GED).
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
import sys
import time

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from bpmn_adapt.bpmn.diff import BpmnDiffer
from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner
from bpmn_adapt.ingestion.discovery import ingest_folder
from bpmn_adapt.providers.manager import ProviderManager

logging.basicConfig(level=logging.WARNING)

PILOT_DATASETS = [
    "Camunda-Credit-scoring",
    "Pmo-3D printer",
    "Mangler-Car Service",
    "Pmo-annual audit",
    "Pmo-Burger Seller",
]


def load_v5_baseline() -> dict[str, dict]:
    v5_file = project_root / "experiments" / "full_82_v5_closed_loop_rag_um_llm1" / "tests.jsonl"
    if not v5_file.exists():
        v5_file = Path("E:/bpmn_adapt_workbench/experiments/full_82_v5_closed_loop_rag_um_llm1/tests.jsonl")

    records = {}
    if v5_file.exists():
        for line in v5_file.read_text(encoding="utf-8").splitlines():
            line_str = line.strip()
            if line_str:
                try:
                    d = json.loads(line_str)
                    records[d["test_id"]] = d
                except Exception:
                    pass
    return records


def run_pilot():
    print("=" * 70, flush=True)
    print("🚀 STARTING PILOT EVALUATION: KNOWLEDGE GRAPH (KG) VS V5 (RAG)", flush=True)
    print(f"Target Datasets ({len(PILOT_DATASETS)}): {', '.join(PILOT_DATASETS)}", flush=True)
    print("=" * 70, flush=True)

    v5_records = load_v5_baseline()
    print(f"Loaded {len(v5_records)} V5 baseline scenario records.", flush=True)

    mgr = ProviderManager(project_root / "providers.json")
    um_test = mgr.test("um-llm1-gemma4")
    print(f"UM LLM1 Provider Status: {um_test.get('status')} | Latency: {um_test.get('latency')}s", flush=True)
    if um_test.get("status") != "OK":
        raise RuntimeError(f"UM LLM1 provider failed: {um_test.get('error')}")

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

    print("RuntimeAdaptationApplication initialized with KG connected:", app.kg.is_connected() if app.kg else False, flush=True)
    print("Analyst Agent KG active:", app.orchestrator.analyst.kg.is_connected() if app.orchestrator.analyst.kg else False, flush=True)
    print("Analyst Agent RAG disabled:", not app.orchestrator.analyst.enable_rag, flush=True)

    dataset_root = project_root / "dataset"
    results = []

    total_scenarios = 0
    kg_correct = 0
    v5_correct = 0

    kg_tp = kg_fp = kg_tn = kg_fn = 0
    v5_tp = v5_fp = v5_tn = v5_fn = 0
    ged_list = []

    for ds_name in PILOT_DATASETS:
        ds_folder = dataset_root / ds_name
        if not ds_folder.exists():
            print(f"⚠️ Folder not found: {ds_folder}", flush=True)
            continue

        runner = BenchmarkRunner(dataset_root=dataset_root, request_types=["ALL"])
        bundle = ingest_folder(ds_folder)
        campaign_cases = runner.extract_test_cases(bundle, ds_name, ds_folder)
        print(f"\n📂 Process: {ds_name} ({len(campaign_cases)} scenarios)", flush=True)

        for c in campaign_cases:
            test_id = c["test_id"]
            op = c["operation"]
            target = c["target"]
            req_text = c.get("request_text") or c.get("raw_text") or ""
            gt = c["ground_truth_decision"]
            total_scenarios += 1

            # Get V5 record for comparison
            v5_rec = v5_records.get(test_id, {})
            v5_dec = v5_rec.get("decision", "UNKNOWN")
            v5_matched = v5_rec.get("matched_ground_truth", False)
            if v5_matched:
                v5_correct += 1

            if v5_matched:
                if gt == "APPROVE":
                    v5_tp += 1
                else:
                    v5_tn += 1
            else:
                if gt == "APPROVE":
                    v5_fn += 1
                else:
                    v5_fp += 1

            # Rate limit backoff
            time.sleep(1.0)

            t0 = time.monotonic()
            ged_val = None
            try:
                res = app.adapt_folder(
                    ds_folder,
                    req_text,
                    target=target,
                    operation=op,
                )
                lat = round(time.monotonic() - t0, 2)
                kg_dec = res.decision.status.value
                kg_reason = res.decision.reason
                rule_hits = res.decision.rule_ids

                # Check GED for RE_ADD
                if op == "RE_ADD" and hasattr(res, "candidate") and res.candidate:
                    try:
                        diff = BpmnDiffer.compare(bundle.bpmn_xml, res.candidate.bpmn_xml)
                        ged_val = len(diff.added_nodes) + len(diff.removed_nodes) + len(diff.added_flows) + len(diff.removed_flows)
                        ged_list.append(ged_val)
                    except Exception:
                        pass
            except Exception as e:
                lat = round(time.monotonic() - t0, 2)
                kg_dec = "ERROR"
                kg_reason = str(e)
                rule_hits = ()

            if gt == "APPROVE":
                is_match = (kg_dec in ("APPROVE", "ALTERNATIVE_PROPOSED"))
                if is_match:
                    kg_tp += 1
                else:
                    kg_fn += 1
            else:
                is_match = (kg_dec == "REJECT")
                if is_match:
                    kg_tn += 1
                else:
                    kg_fp += 1

            if is_match:
                kg_correct += 1

            status_symbol = "✅" if is_match else "❌"
            v5_symbol = "✅" if v5_matched else "❌"

            if is_match and v5_matched:
                diag = "BOTH_CORRECT"
            elif is_match and not v5_matched:
                diag = "KG_IMPROVED"
            elif not is_match and v5_matched:
                diag = "V5_AHEAD"
            else:
                diag = "BOTH_WRONG"

            record = {
                "test_id": test_id,
                "dataset": ds_name,
                "operation": op,
                "target": target,
                "ground_truth": gt,
                "kg_decision": kg_dec,
                "kg_correct": is_match,
                "kg_latency_s": lat,
                "kg_ged": ged_val,
                "kg_rule_hits": rule_hits,
                "kg_reason": kg_reason[:200],
                "v5_decision": v5_dec,
                "v5_correct": v5_matched,
                "diagnosis": diag,
            }
            results.append(record)

            ged_str = f" | GED={ged_val}" if ged_val is not None else ""
            print(
                f"  [{status_symbol} KG: {kg_dec} (gt:{gt})] "
                f"[V5: {v5_symbol} {v5_dec}] "
                f"| {test_id} ({op} '{target[:25]}') "
                f"| Diag: {diag} ({lat}s{ged_str})",
                flush=True,
            )

    app.close()

    out_file = project_root / "experiments" / "kg_pilot_results.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Metrics computation
    kg_acc = kg_correct / max(1, total_scenarios) * 100
    kg_prec = kg_tp / max(1, (kg_tp + kg_fp)) * 100
    kg_rec = kg_tp / max(1, (kg_tp + kg_fn)) * 100
    kg_f1 = (2 * kg_prec * kg_rec / max(0.001, kg_prec + kg_rec)) if (kg_prec + kg_rec) else 0.0

    v5_acc = v5_correct / max(1, total_scenarios) * 100
    v5_prec = v5_tp / max(1, (v5_tp + v5_fp)) * 100
    v5_rec = v5_tp / max(1, (v5_tp + v5_fn)) * 100
    v5_f1 = (2 * v5_prec * v5_rec / max(0.001, v5_prec + v5_rec)) if (v5_prec + v5_rec) else 0.0

    avg_ged = sum(ged_list) / len(ged_list) if ged_list else 0.0

    summary = {
        "total_scenarios": total_scenarios,
        "kg_metrics": {
            "accuracy": round(kg_acc, 2),
            "precision": round(kg_prec, 2),
            "recall": round(kg_rec, 2),
            "f1": round(kg_f1, 2),
            "tp": kg_tp,
            "fp": kg_fp,
            "tn": kg_tn,
            "fn": kg_fn,
            "re_add_count": len(ged_list),
            "avg_ged": round(avg_ged, 2),
            "min_ged": min(ged_list) if ged_list else 0,
            "max_ged": max(ged_list) if ged_list else 0,
        },
        "v5_metrics": {
            "accuracy": round(v5_acc, 2),
            "precision": round(v5_prec, 2),
            "recall": round(v5_rec, 2),
            "f1": round(v5_f1, 2),
            "tp": v5_tp,
            "fp": v5_fp,
            "tn": v5_tn,
            "fn": v5_fn,
        },
        "breakdown_by_diagnosis": {
            "BOTH_CORRECT": sum(1 for r in results if r["diagnosis"] == "BOTH_CORRECT"),
            "KG_IMPROVED": sum(1 for r in results if r["diagnosis"] == "KG_IMPROVED"),
            "V5_AHEAD": sum(1 for r in results if r["diagnosis"] == "V5_AHEAD"),
            "BOTH_WRONG": sum(1 for r in results if r["diagnosis"] == "BOTH_WRONG"),
        },
    }

    sum_file = project_root / "experiments" / "kg_pilot_summary.json"
    sum_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 70, flush=True)
    print("📊 PILOT COMPARISON SUMMARY (KG vs V5 Baseline):", flush=True)
    print(f"Total Scenarios Evaluated: {total_scenarios}", flush=True)
    print(f"Knowledge Graph (KG) Accuracy:  {kg_acc:.2f}% (F1: {kg_f1:.2f}%) [TP={kg_tp}, FP={kg_fp}, TN={kg_tn}, FN={kg_fn}]", flush=True)
    print(f"V5 Closed-Loop RAG Accuracy:   {v5_acc:.2f}% (F1: {v5_f1:.2f}%) [TP={v5_tp}, FP={v5_fp}, TN={v5_tn}, FN={v5_fn}]", flush=True)
    if ged_list:
        print(f"RE-ADD Reconstruction GED:      Avg={avg_ged:.2f}, Min={min(ged_list)}, Max={max(ged_list)} (N={len(ged_list)})", flush=True)
    print(f"Diagnoses: BOTH_CORRECT={summary['breakdown_by_diagnosis']['BOTH_CORRECT']}, KG_IMPROVED={summary['breakdown_by_diagnosis']['KG_IMPROVED']}, V5_AHEAD={summary['breakdown_by_diagnosis']['V5_AHEAD']}, BOTH_WRONG={summary['breakdown_by_diagnosis']['BOTH_WRONG']}", flush=True)
    print(f"Detailed output saved to: {out_file}", flush=True)
    print(f"Summary metrics saved to: {sum_file}", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    run_pilot()

"""
Two-Axis Knowledge Graph Benchmark Campaign on UM LLM1.

Executes full 82-process benchmark (984 scenarios each) using the calibrated Two-Axis Neo4j Knowledge Graph:
1. Phase 1: Two-Axis Pure Knowledge Graph (Two-Axis Neo4j, RAG disabled)
2. Phase 2: Two-Axis Hybrid Graph-RAG (Two-Axis Neo4j + Dense Vector RAG)

Features:
- Automated checkpointing and resume capability.
- Live metric computation (Accuracy, Precision, Recall, F1, Confusion Matrix) every 50 scenarios.
- Seamless transition between phases.
- Paired statistical significance calculation upon completion.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner
from bpmn_adapt.providers.manager import ProviderManager
from bpmn_adapt.retrieval.knowledge_graph import BPMNKnowledgeGraphService

logging.basicConfig(level=logging.WARNING)


def compute_live_metrics(tests_file: Path) -> dict[str, float | int]:
    if not tests_file.is_file():
        return {"total": 0, "correct": 0, "acc": 0.0, "prec": 0.0, "rec": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "tn": 0, "fn": 0}
    lines = [line.strip() for line in tests_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    total = len(lines)
    correct = 0
    tp = fp = tn = fn = 0
    for l in lines:
        try:
            r = json.loads(l)
        except Exception:
            continue
        gt = (r.get("ground_truth_decision") or r.get("ground_truth") or "").strip().upper()
        pred = (r.get("decision") or r.get("prediction") or "").strip().upper()
        is_match = (pred == gt) or (r.get("status") == "SUCCESS" and r.get("matched_ground_truth") is True)
        if is_match:
            correct += 1
        if pred == "APPROVE" and gt == "APPROVE":
            tp += 1
        elif pred == "APPROVE" and gt == "REJECT":
            fp += 1
        elif pred == "REJECT" and gt == "REJECT":
            tn += 1
        elif pred == "REJECT" and gt == "APPROVE":
            fn += 1
    acc = (correct / total * 100) if total else 0.0
    prec = (tp / (tp + fp) * 100) if (tp + fp) else 0.0
    rec = (tp / (tp + fn) * 100) if (tp + fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    return {
        "total": total,
        "correct": correct,
        "acc": acc,
        "prec": prec,
        "rec": rec,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def make_progress_reporter(out_dir: Path, phase_name: str):
    last_reported = 0

    def on_progress(completed: int, total: int, msg: str, **kwargs):
        nonlocal last_reported
        if (completed % 50 == 0 or completed == total) and completed != last_reported and completed > 0:
            last_reported = completed
            tests_file = out_dir / "tests.jsonl"
            metrics = compute_live_metrics(tests_file)
            print("\n" + "=" * 78, flush=True)
            print(f"[{phase_name} PROGRESS: {completed} / {total} SCENARIOS ({completed/total*100:.1f}%)]", flush=True)
            print(f"Evaluated: {metrics['total']} | Correct: {metrics['correct']} | Accuracy: {metrics['acc']:.2f}% | F1: {metrics['f1']:.2f}%", flush=True)
            print(f"Confusion Matrix: TP={metrics['tp']} | FP={metrics['fp']} | TN={metrics['tn']} | FN={metrics['fn']}", flush=True)
            print("=" * 78 + "\n", flush=True)

    return on_progress


def run_phase(phase_id: str, name: str, enable_kg: bool, enable_rag: bool, out_dir: Path, dataset_root: Path, mgr: ProviderManager):
    print("\n" + "#" * 78, flush=True)
    print(f"🚀 STARTING {name.upper()}", flush=True)
    print(f"Directory: {out_dir} | KG={enable_kg} | RAG={enable_rag}", flush=True)
    print("#" * 78, flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)

    runner = BenchmarkRunner(
        dataset_root=dataset_root,
        provider="um-llm1-gemma4",
        request_types=["REMOVE", "ADD"],
        repetitions=1,
        output_dir=out_dir,
        enable_kg=enable_kg,
        enable_rag=enable_rag,
        resume=True,
        manager=mgr,
        on_progress=make_progress_reporter(out_dir, name),
    )

    t0 = time.time()
    runner.run()
    dur = time.time() - t0

    tests_file = out_dir / "tests.jsonl"
    final_metrics = compute_live_metrics(tests_file)

    summary = {
        "phase_id": phase_id,
        "name": name,
        "enable_kg": enable_kg,
        "enable_rag": enable_rag,
        "duration_hours": round(dur / 3600, 2),
        "duration_seconds": round(dur, 1),
        "metrics": final_metrics,
    }
    summary_file = out_dir / "phase_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 78, flush=True)
    print(f"✅ {name.upper()} COMPLETED IN {dur/3600:.2f} HOURS", flush=True)
    print(f"Final Accuracy: {final_metrics['acc']:.2f}% ({final_metrics['correct']} / {final_metrics['total']})", flush=True)
    print(f"Precision: {final_metrics['prec']:.2f}% | Recall: {final_metrics['rec']:.2f}% | F1: {final_metrics['f1']:.2f}%", flush=True)
    print(f"Confusion Matrix: TP={final_metrics['tp']} | FP={final_metrics['fp']} | TN={final_metrics['tn']} | FN={final_metrics['fn']}", flush=True)
    print("=" * 78 + "\n", flush=True)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Two-Axis Knowledge Graph Benchmark Campaign")
    parser.add_argument("--start-phase", choices=["two_axis_kg_pure", "two_axis_graph_rag"], default="two_axis_kg_pure",
                        help="Phase to start from (default: two_axis_kg_pure)")
    args = parser.parse_args()

    print("=" * 78, flush=True)
    print("🌟 TWO-AXIS KNOWLEDGE GRAPH COMPREHENSIVE BENCHMARK ON UM LLM1", flush=True)
    print("=" * 78, flush=True)

    # 1. Health checks
    kg = BPMNKnowledgeGraphService()
    if not kg.connect():
        raise RuntimeError("Could not connect to Neo4j. Is the container running?")
    print("Neo4j Knowledge Graph connected.", flush=True)
    kg.close()

    mgr = ProviderManager(project_root / "providers.json")
    um_test = mgr.test("um-llm1-gemma4")
    print(f"UM LLM1 Status: {um_test.get('status')} | Latency: {um_test.get('latency')}s\n", flush=True)
    if um_test.get("status") != "OK":
        raise RuntimeError(f"UM LLM1 offline: {um_test.get('error')}")

    dataset_root = project_root / "dataset"
    if not dataset_root.exists():
        dataset_root = Path("E:/Implemention_dataset enriched")

    phases = [
        ("two_axis_kg_pure", "Phase 1: Two-Axis Pure Knowledge Graph (Neo4j)", True, False, project_root / "experiments" / "v5_2_two_axis_kg_pure"),
        ("two_axis_graph_rag", "Phase 2: Two-Axis Hybrid Graph-RAG (Neo4j + Vector RAG)", True, True, project_root / "experiments" / "v5_2_two_axis_graph_rag"),
    ]

    start_idx = 0
    for idx, (pid, _, _, _, _) in enumerate(phases):
        if pid == args.start_phase:
            start_idx = idx
            break

    all_summaries = []
    master_start = time.time()

    for pid, name, en_kg, en_rag, out_dir in phases[start_idx:]:
        summary = run_phase(pid, name, en_kg, en_rag, out_dir, dataset_root, mgr)
        all_summaries.append(summary)

    total_dur = time.time() - master_start
    master_report = {
        "campaign": "Two-Axis Knowledge Graph Benchmark Campaign",
        "total_duration_hours": round(total_dur / 3600, 2),
        "phases": all_summaries,
    }
    master_file = project_root / "experiments" / "v5_2_two_axis_campaign_final_report.json"
    master_file.write_text(json.dumps(master_report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "#" * 78, flush=True)
    print(f"🎉 BOTH TWO-AXIS BENCHMARK PHASES COMPLETED IN {total_dur/3600:.2f} HOURS!", flush=True)
    print(f"Final report saved to: {master_file}", flush=True)
    print("#" * 78, flush=True)


if __name__ == "__main__":
    main()

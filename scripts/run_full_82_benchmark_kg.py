"""
Full 82-Process Benchmark Campaign: Knowledge Graph (Neo4j HKG) on UM LLM1.

Evaluates 984 benchmark scenarios (82 processes x 12 scenarios: 6 REMOVE + 6 ADD).
Pure Knowledge Graph Mode (Flat RAG disabled, Neo4j Multi-Hop Structural Reasoning active).
Closed-loop verification with Modeler, Experimenter, and Automated Validation.
Automated checkpointing, live progress reporting every 50 scenarios, and statistical McNemar testing.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner
from bpmn_adapt.providers.manager import ProviderManager
from bpmn_adapt.retrieval.knowledge_graph import BPMNKnowledgeGraphService


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
        gt = r.get("ground_truth_decision", "APPROVE")
        pred = r.get("decision", "ERROR")
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
            print(f"[{phase_name} PROGRESS UPDATE: {completed} / {total} SCENARIOS ({completed/total*100:.1f}%)]", flush=True)
            print(f"Total Evaluated: {metrics['total']} | Correct Decisions: {metrics['correct']}", flush=True)
            print(f"Accuracy:  {metrics['acc']:.2f}%", flush=True)
            print(f"Precision: {metrics['prec']:.2f}%", flush=True)
            print(f"Recall:    {metrics['rec']:.2f}%", flush=True)
            print(f"F1-Score:  {metrics['f1']:.2f}%", flush=True)
            print(f"Confusion Matrix: TP={metrics['tp']} | FP={metrics['fp']} | TN={metrics['tn']} | FN={metrics['fn']}", flush=True)
            print("=" * 78 + "\n", flush=True)

    return on_progress


def run_kg_campaign(max_processes: int | None = None):
    print("=" * 78, flush=True)
    print("🚀 INITIATING FULL 82-PROCESS BENCHMARK CAMPAIGN (KNOWLEDGE GRAPH - NEO4J)", flush=True)
    print("=" * 78, flush=True)

    # 1. Verify Neo4j connection
    kg = BPMNKnowledgeGraphService()
    if not kg.connect():
        raise RuntimeError("Could not connect to Neo4j. Is the Docker container running?")
    print("Neo4j Knowledge Graph connected successfully.", flush=True)
    kg.close()

    # 2. Verify LLM Provider
    mgr = ProviderManager(project_root / "providers.json")
    um_test = mgr.test("um-llm1-gemma4")
    print(f"UM LLM1 Provider Status: {um_test.get('status')} | Latency: {um_test.get('latency')}s", flush=True)
    if um_test.get("status") != "OK":
        raise RuntimeError(f"UM LLM1 is offline or failing: {um_test.get('error')}")

    dataset_root = project_root / "dataset"
    if not dataset_root.exists():
        dataset_root = Path("E:/Implemention_dataset enriched")

    out_dir = project_root / "experiments" / "full_82_kg_neo4j_um_llm1"
    out_dir.mkdir(parents=True, exist_ok=True)

    datasets_filter = None
    if max_processes is not None:
        all_dirs = sorted([d.name for d in dataset_root.iterdir() if d.is_dir() and not d.name.startswith(".")])
        datasets_filter = all_dirs[:max_processes]
        print(f"Limited run to {len(datasets_filter)} processes: {datasets_filter}", flush=True)

    runner = BenchmarkRunner(
        dataset_root=dataset_root,
        provider="um-llm1-gemma4",
        request_types=["REMOVE", "ADD"],
        repetitions=1,
        output_dir=out_dir,
        enable_rag=False,  # Pure KG mode: Flat RAG disabled
        resume=True,
        manager=mgr,
        datasets=datasets_filter,
        on_progress=make_progress_reporter(out_dir, "KG NEO4J CAMPAIGN"),
    )

    t0 = time.time()
    runner.run()
    dur = time.time() - t0

    print("\n" + "#" * 78, flush=True)
    print(f"🎉 FULL KG CAMPAIGN FINISHED IN {dur/3600:.2f} HOURS ({dur:.1f}s)", flush=True)
    print("#" * 78, flush=True)

    tests_file = out_dir / "tests.jsonl"
    final_metrics = compute_live_metrics(tests_file)
    print(f"Final Evaluated: {final_metrics['total']} | Accuracy: {final_metrics['acc']:.2f}% | F1: {final_metrics['f1']:.2f}%", flush=True)
    print(f"Confusion Matrix: TP={final_metrics['tp']} | FP={final_metrics['fp']} | TN={final_metrics['tn']} | FN={final_metrics['fn']}", flush=True)


if __name__ == "__main__":
    max_p = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_kg_campaign(max_processes=max_p)

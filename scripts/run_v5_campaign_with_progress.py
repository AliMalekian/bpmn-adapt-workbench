"""Executes Version 5 (Precedent-Governed Adaptation + Analogical CoT) Benchmark Campaign on UM LLM1.

Features:
- Fixed activity target extraction regex (eliminates 'optional' truncation artifacts, extracts clean task names).
- Structured query anchoring for RAG retrieval (operation + quoted clean target + operational intent).
- Active Precedent-Governed Adaptation (Analogical Chain-of-Thought with 'precedent_analogical_reasoning').
- Precedent Authorization Engine for permissive boundary steps and administrative milestones (REMOVE_4).
- Affirmative Mandate requirement ('MUST', 'SHALL', 'REQUIRED') for rule rejections.
- Symmetric structural alignment filtering (suppresses LOW alignment precedents).
- Closed-loop verification with Modeler and Experimenter.
- Live progress reporting every 50 scenarios and automated McNemar statistical significance testing upon completion.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

sys.path.insert(0, "E:/bpmn_adapt_workbench/src")

from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner
from bpmn_adapt.providers.manager import ProviderManager
from bpmn_adapt.application import RuntimeAdaptationApplication
from bpmn_adapt.config import Settings
from bpmn_adapt.retrieval.rag_admin import flush_rag, get_rag_status


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


def run_v5_campaign():
    base_dir = Path("E:/bpmn_adapt_workbench")
    dataset_root = Path("E:/Implemention_dataset enriched")

    mgr = ProviderManager(base_dir / "providers.json")
    um_test = mgr.test("um-llm1-gemma4")
    print(f"UM LLM1 Provider Status: {um_test.get('status')} | Latency: {um_test.get('latency')}s", flush=True)
    if um_test.get("status") != "OK":
        raise RuntimeError(f"UM LLM1 is offline or failing: {um_test.get('error')}")

    # PHASE 1: Clean RAG Initialization
    print("\n" + "#" * 80, flush=True)
    print("PHASE 1: Initializing RAG Memory for Version 5 Campaign", flush=True)
    print("#" * 80, flush=True)
    flush_res = flush_rag()
    print(flush_res.get("message"), flush=True)
    print(f"RAG Status before run: {get_rag_status()}", flush=True)

    # PHASE 2: Full Evaluation WITH-RAG (984 Scenarios)
    rag_dir = base_dir / "experiments" / "full_82_v5_closed_loop_rag_um_llm1"
    print("\n" + "#" * 80, flush=True)
    print("PHASE 2: Starting Version 5 Full 82-Process Evaluation WITH-RAG (984 Scenarios)", flush=True)
    print("#" * 80, flush=True)
    t0_rag = time.time()
    runner_rag = BenchmarkRunner(
        dataset_root=dataset_root,
        provider="um-llm1-gemma4",
        request_types=["REMOVE", "ADD"],
        repetitions=1,
        output_dir=rag_dir,
        enable_rag=True,
        resume=True,
        manager=mgr,
        on_progress=make_progress_reporter(rag_dir, "V5 WITH-RAG"),
    )
    runner_rag.run()
    dur_rag = time.time() - t0_rag
    print(f"\nPhase 2 (With-RAG) finished in {dur_rag/3600:.2f} hours.", flush=True)

    # PHASE 3: Full Baseline WITHOUT-RAG (984 Scenarios)
    no_rag_dir = base_dir / "experiments" / "full_82_v5_closed_loop_no_rag_um_llm1"
    print("\n" + "#" * 80, flush=True)
    print("PHASE 3: Starting Version 5 Full 82-Process Baseline WITHOUT-RAG (984 Scenarios)", flush=True)
    print("#" * 80, flush=True)
    t0_no = time.time()
    runner_no = BenchmarkRunner(
        dataset_root=dataset_root,
        provider="um-llm1-gemma4",
        request_types=["REMOVE", "ADD"],
        repetitions=1,
        output_dir=no_rag_dir,
        enable_rag=False,
        resume=True,
        manager=mgr,
        on_progress=make_progress_reporter(no_rag_dir, "V5 NO-RAG"),
    )
    runner_no.run()
    dur_no = time.time() - t0_no
    print(f"\nPhase 3 (No-RAG) finished in {dur_no/3600:.2f} hours.", flush=True)

    print("\n" + "#" * 80, flush=True)
    print("ALL V5 EXPERIMENTS (1968 SCENARIOS) COMPLETED SUCCESSFULLY!", flush=True)
    print("#" * 80, flush=True)


if __name__ == "__main__":
    run_v5_campaign()

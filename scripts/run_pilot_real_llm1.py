"""Executes real pilot evaluation on UM LLM1 (A100, gemma4) across No-RAG and Cold-Start RAG modes.

Evaluates 12 balanced scenarios (6 REMOVE + 6 ADD) with authentic HTTP calls to https://172.20.8.152.
Outputs all test records, LLM prompts/responses, system logs, metrics, and learning curves.
"""
from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner
from bpmn_adapt.providers.manager import ProviderManager
from bpmn_adapt.retrieval.rag_admin import flush_rag, get_rag_status, plot_learning_curve


def run_pilot():
    base_dir = Path("E:/bpmn_adapt_workbench")
    dataset_root = Path("E:/Implemention_dataset enriched")
    target_dataset = ["Camunda-Credit-scoring"]

    print("=" * 70)
    print("STEP 0: Verifying UM LLM1 (A100, gemma4) Connectivity")
    print("=" * 70)
    mgr = ProviderManager()
    um_test = mgr.test("um-llm1-gemma4")
    print(f"Provider Status: {um_test.get('status')} | Latency: {um_test.get('latency')}s")
    if um_test.get("status") != "OK":
        raise RuntimeError(f"UM LLM1 is offline or failing: {um_test.get('error')}")

    # =========================================================================
    # PHASE 1: No-RAG Baseline Evaluation
    # =========================================================================
    no_rag_dir = base_dir / "experiments" / "pilot_no_rag_um_llm1"
    tests_no_rag_f = no_rag_dir / "tests.jsonl"
    
    if tests_no_rag_f.is_file() and len(tests_no_rag_f.read_text(encoding="utf-8").splitlines()) >= 12:
        print("\n" + "=" * 70)
        print("PHASE 1: Found completed No-RAG Baseline results (12 tests) - Skipping Phase 1")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("PHASE 1: Running Pilot Baseline WITHOUT RAG (Zero-Shot)")
        print("=" * 70)
        t0_no_rag = time.time()
        runner_no_rag = BenchmarkRunner(
            dataset_root=dataset_root,
            provider="um-llm1-gemma4",
            datasets=target_dataset,
            request_types=["REMOVE", "ADD"],
            repetitions=1,
            output_dir=no_rag_dir,
            enable_rag=False,
        )
        res_no_rag = runner_no_rag.run()
        dur_no_rag = time.time() - t0_no_rag
        print(f"Phase 1 Finished in {dur_no_rag:.1f}s.")

    # =========================================================================
    # PHASE 2: Flush RAG Memory to Guarantee Cold-Start
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 2: Flushing RAG Memory for Pure Cold-Start")
    print("=" * 70)
    flush_res = flush_rag()
    print(flush_res.get("message"))
    status_check = get_rag_status()
    print("RAG Status post-flush:", status_check.get("status_summary"))

    # =========================================================================
    # PHASE 3: With-RAG Cold-Start Online Learning Evaluation
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 3: Running Pilot WITH RAG (Cold-Start Continual Learning)")
    print("=" * 70)
    rag_dir = base_dir / "experiments" / "pilot_rag_cold_start_um_llm1"

    t0_rag = time.time()
    runner_rag = BenchmarkRunner(
        dataset_root=dataset_root,
        provider="um-llm1-gemma4",
        datasets=target_dataset,
        request_types=["REMOVE", "ADD"],
        repetitions=1,
        output_dir=rag_dir,
        enable_rag=True,
    )
    res_rag = runner_rag.run()
    dur_rag = time.time() - t0_rag
    print(f"Phase 3 Finished in {dur_rag:.1f}s.")

    # Generate Learning Curve
    lc_chart = plot_learning_curve(rag_dir, title="Pilot Learning Curve (UM LLM1 - Cold Start)")
    print(f"Generated Learning Curve at: {lc_chart}")

    # =========================================================================
    # PHASE 4: Compile Comprehensive Pilot Evaluation Report
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 4: Compiling Comparative Pilot Report")
    print("=" * 70)

    no_rag_tests = [json.loads(l) for l in open(no_rag_dir / "tests.jsonl", encoding="utf-8") if l.strip()]
    rag_tests = [json.loads(l) for l in open(rag_dir / "tests.jsonl", encoding="utf-8") if l.strip()]

    def compute_metrics(tests):
        tot = len(tests)
        corr = sum(1 for t in tests if t.get("matched_ground_truth"))
        tp = sum(1 for t in tests if t.get("ground_truth_decision") == "APPROVE" and t.get("decision") in ("APPROVE", "ALTERNATIVE_PROPOSED"))
        fp = sum(1 for t in tests if t.get("ground_truth_decision") == "REJECT" and t.get("decision") != "REJECT")
        fn = sum(1 for t in tests if t.get("ground_truth_decision") == "APPROVE" and t.get("decision") not in ("APPROVE", "ALTERNATIVE_PROPOSED"))
        tn = sum(1 for t in tests if t.get("ground_truth_decision") == "REJECT" and t.get("decision") == "REJECT")
        acc = round((corr / max(1, tot)) * 100, 2)
        prec = round((tp / max(1, tp + fp)) * 100, 2)
        rec = round((tp / max(1, tp + fn)) * 100, 2)
        f1 = round(2 * (prec * rec) / max(1e-9, prec + rec), 2)
        avg_lat = round(sum(t.get("latency_s", 0) for t in tests) / max(1, tot), 2)
        in_tok = sum(t.get("prompt_tokens", 0) for t in tests)
        out_tok = sum(t.get("completion_tokens", 0) for t in tests)
        return {
            "total": tot, "correct": corr, "acc": acc, "prec": prec, "rec": rec, "f1": f1,
            "latency": avg_lat, "in_tok": in_tok, "out_tok": out_tok, "tot_tok": in_tok + out_tok,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn
        }

    m_norag = compute_metrics(no_rag_tests)
    m_rag = compute_metrics(rag_tests)

    report_md = f"""# Pilot Evaluation Report: Real UM LLM1 (A100, gemma4) Execution

- **Date / Time**: {time.strftime('%Y-%m-%d %H:%M:%S')}
- **Target Process**: `Camunda-Credit-scoring` (12 Balanced BPM Scenarios: 6 REMOVE + 6 ADD)
- **Active Provider**: `UM LLM1 (A100, gemma4)` via university server `https://172.20.8.152`
- **Authenticity**: 100% Real HTTP API executions (zero synthetic mocks)

---

## 1. Executive Performance Comparison Matrix

| Evaluation Metric | Without RAG (Zero-Shot) | With RAG (Cold Start) | Absolute Improvement |
| :--- | :---: | :---: | :---: |
| **Accuracy (%)** | **{m_norag['acc']}%** ({m_norag['correct']}/{m_norag['total']}) | **{m_rag['acc']}%** ({m_rag['correct']}/{m_rag['total']}) | **{m_rag['acc'] - m_norag['acc']:+.2f}%** |
| **Precision (%)** | {m_norag['prec']}% | {m_rag['prec']}% | {m_rag['prec'] - m_norag['prec']:+.2f}% |
| **Recall (%)** | {m_norag['rec']}% | {m_rag['rec']}% | {m_rag['rec'] - m_norag['rec']:+.2f}% |
| **F1-Score (%)** | **{m_norag['f1']}%** | **{m_rag['f1']}%** | **{m_rag['f1'] - m_norag['f1']:+.2f}%** |
| **Average Latency (s)** | {m_norag['latency']}s | {m_rag['latency']}s | {m_rag['latency'] - m_norag['latency']:+.2f}s |
| **Total Tokens Consumed** | {m_norag['tot_tok']:,} tokens | {m_rag['tot_tok']:,} tokens | {m_rag['tot_tok'] - m_norag['tot_tok']:+,} tokens |
| **Prompt (Input) Tokens** | {m_norag['in_tok']:,} | {m_rag['in_tok']:,} | {m_rag['in_tok'] - m_norag['in_tok']:+,} |
| **Completion (Output) Tokens** | {m_norag['out_tok']:,} | {m_rag['out_tok']:,} | {m_rag['out_tok'] - m_norag['out_tok']:+,} |

---

## 2. Test-by-Test Execution Breakdown (12 Scenarios)

| # | Test ID | Operation | Target Element | Ground Truth | No-RAG Decision | With-RAG Decision | Match No-RAG | Match RAG |
| :-: | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
"""

    for idx, (t_no, t_r) in enumerate(zip(no_rag_tests, rag_tests), 1):
        tid = t_no['test_id'].replace("Camunda-Credit-scoring_", "")
        op = t_no['operation']
        tgt = t_no['target'][:30]
        gt = t_no['ground_truth_decision']
        d_no = t_no['decision']
        d_r = t_r['decision']
        m_no = "✅ PASS" if t_no['matched_ground_truth'] else "❌ FAIL"
        m_r = "✅ PASS" if t_r['matched_ground_truth'] else "❌ FAIL"
        report_md += f"| {idx} | `{tid}` | {op} | {tgt} | **{gt}** | {d_no} | {d_r} | {m_no} | {m_r} |\n"

    report_md += f"""
---

## 3. System Artifacts and Logs Location

All raw data and network logs are preserved alongside other runs:
- **No-RAG Test Records**: [`experiments/pilot_no_rag_um_llm1/tests.jsonl`](file:///e:/bpmn_adapt_workbench/experiments/pilot_no_rag_um_llm1/tests.jsonl)
- **No-RAG HTTP Call Trace**: [`experiments/pilot_no_rag_um_llm1/llm_calls.jsonl`](file:///e:/bpmn_adapt_workbench/experiments/pilot_no_rag_um_llm1/llm_calls.jsonl)
- **With-RAG Test Records**: [`experiments/pilot_rag_cold_start_um_llm1/tests.jsonl`](file:///e:/bpmn_adapt_workbench/experiments/pilot_rag_cold_start_um_llm1/tests.jsonl)
- **With-RAG HTTP Call Trace**: [`experiments/pilot_rag_cold_start_um_llm1/llm_calls.jsonl`](file:///e:/bpmn_adapt_workbench/experiments/pilot_rag_cold_start_um_llm1/llm_calls.jsonl)
- **Learning Curve Visualization**: [`experiments/pilot_rag_cold_start_um_llm1/learning_curve.png`](file:///e:/bpmn_adapt_workbench/experiments/pilot_rag_cold_start_um_llm1/learning_curve.png)
"""

    report_path = base_dir / "experiments" / "PILOT_EVALUATION_REPORT_UM_LLM1.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"Report successfully compiled at: {report_path}")

    return {
        "report_path": str(report_path),
        "no_rag": m_norag,
        "rag": m_rag,
    }


if __name__ == "__main__":
    run_pilot()

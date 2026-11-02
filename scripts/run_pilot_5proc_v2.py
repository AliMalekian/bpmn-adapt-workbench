"""Executes 5-process multi-dataset pilot evaluation V2 on UM LLM1 (A100, gemma4).

Evaluates 60 balanced scenarios across 5 diverse BPMN processes:
1. Camunda-Credit-scoring
2. Camunda-Dispatch of goods
3. Camunda-Recource
4. Camunda-Self-service-restaurant
5. Mangler-App For Participating at the Vienna Night Run

Tests both No-RAG and Cold-Start With-RAG with:
- Gated RAG Indexing (excluding AMBIGUOUS_REQUEST)
- Unambiguous Optional Step Feasibility
- Cross-Process Precedent Retrieval
"""
from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner
from bpmn_adapt.providers.manager import ProviderManager
from bpmn_adapt.retrieval.rag_admin import flush_rag, get_rag_status, plot_learning_curve


def run_5proc_v2():
    base_dir = Path("E:/bpmn_adapt_workbench")
    dataset_root = Path("E:/Implemention_dataset enriched")
    target_datasets = [
        "Camunda-Credit-scoring",
        "Camunda-Dispatch of goods",
        "Camunda-Recource",
        "Camunda-Self-service-restaurant",
        "Mangler-App For Participating at the Vienna Night Run",
    ]

    print("=" * 75)
    print("STEP 0: Verifying UM LLM1 (A100, gemma4) Connectivity via University LAN")
    print("=" * 75)
    mgr = ProviderManager(base_dir / "providers.json")
    um_test = mgr.test("um-llm1-gemma4")
    print(f"Provider Status: {um_test.get('status')} | Latency: {um_test.get('latency')}s")
    if um_test.get("status") != "OK":
        raise RuntimeError(f"UM LLM1 is offline or failing: {um_test.get('error')}")

    # =========================================================================
    # PHASE 1: No-RAG Baseline Evaluation (60 Scenarios)
    # =========================================================================
    no_rag_dir = base_dir / "experiments" / "pilot_5proc_v2_no_rag_um_llm1"
    print("\n" + "=" * 75)
    print("PHASE 1: Running 5-Process V2 Baseline WITHOUT RAG (Zero-Shot)")
    print("=" * 75)
    t0_no_rag = time.time()
    runner_no_rag = BenchmarkRunner(
        dataset_root=dataset_root,
        provider="um-llm1-gemma4",
        datasets=target_datasets,
        request_types=["REMOVE", "ADD"],
        repetitions=1,
        output_dir=no_rag_dir,
        enable_rag=False,
    )
    res_no_rag = runner_no_rag.run()
    dur_no_rag = time.time() - t0_no_rag
    print(f"Phase 1 Finished in {dur_no_rag:.1f}s.")

    # =========================================================================
    # PHASE 2: Flush RAG Memory to Guarantee Pure Cold-Start
    # =========================================================================
    print("\n" + "=" * 75)
    print("PHASE 2: Flushing RAG Memory for Pure Cold-Start")
    print("=" * 75)
    flush_res = flush_rag()
    print(flush_res.get("message"))
    status_check = get_rag_status()
    print("RAG Status post-flush:", status_check.get("status_summary"))

    # =========================================================================
    # PHASE 3: With-RAG Cold-Start Online Cross-Process Learning (60 Scenarios)
    # =========================================================================
    print("\n" + "=" * 75)
    print("PHASE 3: Running 5-Process V2 WITH RAG (Gated Continual Learning)")
    print("=" * 75)
    rag_dir = base_dir / "experiments" / "pilot_5proc_v2_rag_cold_start_um_llm1"

    t0_rag = time.time()
    runner_rag = BenchmarkRunner(
        dataset_root=dataset_root,
        provider="um-llm1-gemma4",
        datasets=target_datasets,
        request_types=["REMOVE", "ADD"],
        repetitions=1,
        output_dir=rag_dir,
        enable_rag=True,
    )
    res_rag = runner_rag.run()
    dur_rag = time.time() - t0_rag
    print(f"Phase 3 Finished in {dur_rag:.1f}s.")

    # Generate Learning Curve
    lc_chart = plot_learning_curve(rag_dir, title="5-Process V2 Continual Learning Curve (UM LLM1 - Cold Start)")
    print(f"Generated Learning Curve at: {lc_chart}")

    print("=" * 75)
    print("5-PROCESS V2 PILOT COMPLETED SUCCESSFULLY")
    print("=" * 75)


if __name__ == "__main__":
    run_5proc_v2()

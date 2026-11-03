"""Executes full benchmark evaluation across all 82 datasets (984 scenarios) on UM LLM1.

Evaluates 984 balanced scenarios:
- 492 REMOVE requests (246 REJECT [rule, resource, both] + 246 APPROVE)
- 492 ADD requests (246 REJECT [rule, resource, both] + 246 APPROVE)
- Exactly 50.0% / 50.0% balance.

Runs With-RAG first (cold-start with gated indexing), then No-RAG baseline.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner
from bpmn_adapt.providers.manager import ProviderManager
from bpmn_adapt.retrieval.rag_admin import flush_rag, get_rag_status, plot_learning_curve


def run_full_82_campaign():
    base_dir = Path("E:/bpmn_adapt_workbench")
    dataset_root = Path("E:/Implemention_dataset enriched")

    mgr = ProviderManager(base_dir / "providers.json")
    um_test = mgr.test("um-llm1-gemma4")
    print(f"Provider Status: {um_test.get('status')} | Latency: {um_test.get('latency')}s")
    if um_test.get("status") != "OK":
        raise RuntimeError(f"UM LLM1 is offline or failing: {um_test.get('error')}")

    # PHASE 1: Flush RAG for Clean Cold Start
    print("\n" + "=" * 75)
    print("PHASE 1: Flushing RAG Memory for Clean Cold-Start")
    print("=" * 75)
    flush_res = flush_rag()
    print(flush_res.get("message"))
    print(f"RAG Status before run: {get_rag_status()}")

    # PHASE 2: Full Evaluation WITH RAG (984 Scenarios)
    rag_dir = base_dir / "experiments" / "full_82_clean_rag_um_llm1"
    print("\n" + "=" * 75)
    print("PHASE 2: Starting Full 82-Process Evaluation WITH RAG (Clean Stripped Prompts)")
    print("=" * 75)
    t0_rag = time.time()
    runner_rag = BenchmarkRunner(
        dataset_root=dataset_root,
        provider="um-llm1-gemma4",
        request_types=["REMOVE", "ADD"],
        repetitions=1,
        output_dir=rag_dir,
        enable_rag=True,
        resume=True,
    )
    runner_rag.run()
    dur_rag = time.time() - t0_rag
    print(f"Phase 2 (With RAG) finished in {dur_rag/3600:.2f} hours.")

    # Plot Full Learning Curve
    plot_learning_curve(rag_dir, title="Full 82-Process Continual Learning Curve - Clean Prompts (UM LLM1)")

    # PHASE 3: Full Baseline WITHOUT RAG (984 Scenarios)
    no_rag_dir = base_dir / "experiments" / "full_82_clean_no_rag_um_llm1"
    print("\n" + "=" * 75)
    print("PHASE 3: Starting Full 82-Process Baseline WITHOUT RAG (Clean Stripped Prompts)")
    print("=" * 75)
    t0_no = time.time()
    runner_no = BenchmarkRunner(
        dataset_root=dataset_root,
        provider="um-llm1-gemma4",
        request_types=["REMOVE", "ADD"],
        repetitions=1,
        output_dir=no_rag_dir,
        enable_rag=False,
        resume=True,
    )
    runner_no.run()
    dur_no = time.time() - t0_no
    print(f"Phase 3 (No RAG) finished in {dur_no/3600:.2f} hours.")

    print("\n" + "=" * 75)
    print("Full 82-Process Campaign (Both With-RAG and No-RAG) Successfully Completed!")
    print("=" * 75)


if __name__ == "__main__":
    run_full_82_campaign()

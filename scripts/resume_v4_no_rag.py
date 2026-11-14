"""Resumes Phase 3 (V4 Baseline WITHOUT-RAG) on UM LLM1 from the last completed scenario."""
import sys
import time
from pathlib import Path

sys.path.insert(0, "E:/bpmn_adapt_workbench/src")

from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner
from bpmn_adapt.providers.manager import ProviderManager
from run_v4_campaign_with_progress import compute_live_metrics, make_progress_reporter

def resume_no_rag():
    base_dir = Path("E:/bpmn_adapt_workbench")
    dataset_root = Path("E:/Implemention_dataset enriched")

    mgr = ProviderManager(base_dir / "providers.json")
    um_test = mgr.test("um-llm1-gemma4")
    print(f"UM LLM1 Provider Status: {um_test.get('status')} | Latency: {um_test.get('latency')}s", flush=True)
    if um_test.get("status") != "OK":
        raise RuntimeError(f"UM LLM1 is offline or failing: {um_test.get('error')}")

    no_rag_dir = base_dir / "experiments" / "full_82_v4_closed_loop_no_rag_um_llm1"
    tests_file = no_rag_dir / "tests.jsonl"
    existing_lines = 0
    if tests_file.is_file():
        existing_lines = len([l for l in tests_file.read_text(encoding="utf-8").splitlines() if l.strip()])
    print(f"Found {existing_lines} completed scenarios in {tests_file}. Resuming cleanly...", flush=True)

    print("\n" + "#" * 80, flush=True)
    print(f"RESUMING PHASE 3: V4 Full Baseline WITHOUT-RAG (Starting at scenario {existing_lines + 1} / 984)", flush=True)
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
        on_progress=make_progress_reporter(no_rag_dir, "NO-RAG"),
    )
    runner_no.run()
    dur_no = time.time() - t0_no
    print(f"\nPhase 3 (No-RAG) finished in {dur_no/3600:.2f} hours.", flush=True)
    print("\n" + "#" * 80, flush=True)
    print("V4 NO-RAG BENCHMARK FULLY COMPLETED (984/984 SCENARIOS)!", flush=True)
    print("#" * 80, flush=True)

if __name__ == "__main__":
    resume_no_rag()

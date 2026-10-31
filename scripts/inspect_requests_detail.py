import json
from pathlib import Path
from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.config import Settings

v4_file = Path("experiments/live_evaluation_v4/tests.jsonl")
tests_v4 = {t['test_id']: t for t in (json.loads(l) for l in v4_file.read_text(encoding="utf-8").splitlines() if l.strip())}
norag_file = Path("experiments/live_evaluation_no_rag/tests.jsonl")
tests_norag = {t['test_id']: t for t in (json.loads(l) for l in norag_file.read_text(encoding="utf-8").splitlines() if l.strip())}

both_mismatch = sorted(list(set(t for t, v in tests_v4.items() if not v.get('matched_ground_truth')) & 
                            set(t for t, v in tests_norag.items() if not v.get('matched_ground_truth'))))

print(f"Total common mismatches: {len(both_mismatch)}")
for tid in both_mismatch[:5]:
    t = tests_v4[tid]
    ds_name = t['dataset']
    op = t['operation']
    print("=" * 60)
    print(f"Test ID: {tid} | Op: {op}")
    print(f"Ground Truth Decision in Benchmark: {t.get('ground_truth_decision')}")
    print(f"Model Decision (v4): {t.get('decision')}")
    print(f"Model Decision (norag): {tests_norag[tid].get('decision')}")
    print(f"Request Text:\n{t.get('reason')}")

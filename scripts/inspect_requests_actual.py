import json
from pathlib import Path
from bpmn_adapt.ingestion.discovery import ingest_folder
from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner

runner = BenchmarkRunner(dataset_root="E:/Implemention_dataset enriched", output_dir="experiments/test")
v4_file = Path("experiments/live_evaluation_v4/tests.jsonl")
tests_v4 = {t['test_id']: t for t in (json.loads(l) for l in v4_file.read_text(encoding="utf-8").splitlines() if l.strip())}
norag_file = Path("experiments/live_evaluation_no_rag/tests.jsonl")
tests_norag = {t['test_id']: t for t in (json.loads(l) for l in norag_file.read_text(encoding="utf-8").splitlines() if l.strip())}

both_mismatch = sorted(list(set(t for t, v in tests_v4.items() if not v.get('matched_ground_truth')) & 
                            set(t for t, v in tests_norag.items() if not v.get('matched_ground_truth'))))

for tid in both_mismatch[:5]:
    t = tests_v4[tid]
    ds_name = t['dataset']
    folder = Path("E:/Implemention_dataset enriched") / ds_name
    bundle = ingest_folder(folder)
    cases = runner.extract_test_cases(bundle, ds_name, ds_folder=folder)
    matched_case = next((c for c in cases if c['test_id'] == tid), None)
    print("=" * 60)
    print(f"Test ID: {tid}")
    print(f"GT: {t.get('ground_truth_decision')} | Model v4: {t.get('decision')} | Model norag: {tests_norag[tid].get('decision')}")
    if matched_case:
        print(f"Actual Request Text:\n{matched_case['request_text']}")
    print(f"Model Reasoning v4:\n{t.get('reason')}")

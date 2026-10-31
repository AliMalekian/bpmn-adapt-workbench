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

print(f"Total common mismatches: {len(both_mismatch)}")
gt_false_reject_count = 0
synthetic_add_conflict_count = 0

for tid in both_mismatch:
    t = tests_v4[tid]
    ds_name = t['dataset']
    folder = Path("E:/Implemention_dataset enriched") / ds_name
    bundle = ingest_folder(folder)
    cases = runner.extract_test_cases(bundle, ds_name, ds_folder=folder)
    c = next((item for item in cases if item['test_id'] == tid), None)
    if not c:
        continue
    req_text = c['request_text']
    gt = t.get('ground_truth_decision')
    dec = t.get('decision')
    
    # Check if phrase like 'does not conflict' or 'without conflict' exists
    lower = req_text.lower()
    has_negated_conflict = any(phrase in lower for phrase in ["does not conflict", "not conflict", "without conflict", "no conflict", "no rules or resources are affected", "no operational rule is violated", "fully compliant"])
    
    print(f"ID: {tid} | GT: {gt} | LLM: {dec}")
    if gt == "REJECT" and dec == "APPROVE":
        if has_negated_conflict:
            print("  --> BINGO! Text actually says it DOES NOT conflict / no rules affected, but GT was marked REJECT because the word 'conflict' was found!")
            gt_false_reject_count += 1
    elif gt == "APPROVE" and dec == "REJECT":
        if "quality inspection and verification" in lower:
            print("  --> Synthetic ADD: GT assumed APPROVE, but model found legitimate rule conflict!")
            synthetic_add_conflict_count += 1
        elif "remove" in c['operation'].lower():
            print(f"  --> REMOVE test: GT was APPROVE, but model rejected: {t.get('reason')[:100]}...")

print("=" * 60)
print(f"False REJECT in Ground Truth (due to 'does not conflict' heuristic bug): {gt_false_reject_count}")
print(f"Synthetic ADD conflicts: {synthetic_add_conflict_count}")

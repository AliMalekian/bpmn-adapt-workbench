import json

with open("mock_run_5x82_archive/data/test_execution_manifest.jsonl", "r", encoding="utf-8") as f:
    records = [json.loads(line) for line in f]

errors = [r for r in records if not r["is_correct"]]
print(f"Total errors: {len(errors)} out of {len(records)}")

by_type = {}
for r in errors:
    t = r["test_type"]
    by_type[t] = by_type.get(t, 0) + 1
print("Errors by test_type:", by_type)

fps = [r for r in errors if r["classification"] == "FP"]
print(f"\n--- TOTAL FPs: {len(fps)} ---")
for r in fps[:10]:
    print(f"Dataset: {r['dataset']} | Type: {r['test_type']} | Target: {r['target_element']}")
    print(f"  Pred: {r['predicted_decision']} (GT: {r['ground_truth_decision']}) | Rules: {r['rule_hits']} | Res: {r['resource_hits']}")

fns = [r for r in errors if r["classification"] == "FN"]
print(f"\n--- TOTAL FNs: {len(fns)} ---")
for r in fns[:10]:
    print(f"Dataset: {r['dataset']} | Type: {r['test_type']} | Target: {r['target_element']}")
    print(f"  Pred: {r['predicted_decision']} (GT: {r['ground_truth_decision']}) | Rules: {r['rule_hits']} | Res: {r['resource_hits']}")


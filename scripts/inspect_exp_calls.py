import json

with open("E:/bpmn_adapt_workbench/experiments/live_evaluation_v4/llm_calls.jsonl", "r", encoding="utf-8") as f:
    calls = [json.loads(l) for l in f if l.strip()]

exp_calls = [c for c in calls if c.get("schema_name") == "experiment"]
model_calls = [c for c in calls if c.get("schema_name") == "model"]
print(f"Total model calls: {len(model_calls)}, Total experiment calls: {len(exp_calls)}")

# Let's check when the last 10 model calls were made vs experiment calls
print("\nLast 5 model calls:")
for c in model_calls[-5:]:
    print("  ", c.get("timestamp"), c.get("status"))

print("\nLast 5 experiment calls:")
for c in exp_calls[-5:]:
    print("  ", c.get("timestamp"), c.get("status"))

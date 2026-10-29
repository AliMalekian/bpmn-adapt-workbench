import json

with open("E:/bpmn_adapt_workbench/experiments/live_evaluation_v4/tests.jsonl", "r", encoding="utf-8") as f:
    tests = [json.loads(l) for l in f if l.strip()]

approved_with_sim = [t for t in tests if t.get("decision") == "APPROVE"]
print(f"Total tests: {len(tests)}, Total APPROVE: {len(approved_with_sim)}")

ops = {}
for t in approved_with_sim:
    op = t.get("operation")
    ops[op] = ops.get(op, 0) + 1
print("Approved by operation:", ops)

# How many tests had simulation_success == True?
sim_true = [t for t in tests if t.get("simulation_success")]
print("simulation_success == True count:", len(sim_true))

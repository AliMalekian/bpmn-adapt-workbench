import json
from pathlib import Path

norag = {t['test_id']: t for t in (json.loads(l) for l in Path("experiments/live_evaluation_no_rag/tests.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
v6 = {t['test_id']: t for t in (json.loads(l) for l in Path("experiments/live_evaluation_rag_v6/tests.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
v4 = {t['test_id']: t for t in (json.loads(l) for l in Path("experiments/live_evaluation_v4/tests.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}

print("=== TESTS WHERE v6 MATCHED GT BUT NO-RAG MISMATCHED (RAG v6 HELPED) ===")
for tid, t6 in v6.items():
    tn = norag.get(tid)
    if tn and t6.get("matched_ground_truth") and not tn.get("matched_ground_truth"):
        print(f"Test ID: {tid}")
        print(f"  GT: {t6.get('ground_truth_decision')} | v6: {t6.get('decision')} | norag: {tn.get('decision')}")
        print(f"  v6 Reason: {t6.get('reason')[:100]}...")

print("\n=== TESTS WHERE NO-RAG MATCHED GT BUT v6 MISMATCHED (v6 FAILED) ===")
for tid, t6 in v6.items():
    tn = norag.get(tid)
    if tn and not t6.get("matched_ground_truth") and tn.get("matched_ground_truth"):
        print(f"Test ID: {tid}")
        print(f"  GT: {t6.get('ground_truth_decision')} | v6: {t6.get('decision')} | norag: {tn.get('decision')}")
        print(f"  v6 Reason: {t6.get('reason')[:120]}...")
        print(f"  norag Reason: {tn.get('reason')[:120]}...")

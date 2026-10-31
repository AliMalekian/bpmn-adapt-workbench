import json
from pathlib import Path

v4_file = Path("experiments/live_evaluation_v4/tests.jsonl")
norag_file = Path("experiments/live_evaluation_no_rag/tests.jsonl")

tests_v4 = {t['test_id']: t for t in (json.loads(l) for l in v4_file.read_text(encoding="utf-8").splitlines() if l.strip())}
tests_norag = {t['test_id']: t for t in (json.loads(l) for l in norag_file.read_text(encoding="utf-8").splitlines() if l.strip())}

mismatch_v4 = {tid: t for tid, t in tests_v4.items() if not t.get('matched_ground_truth')}
mismatch_norag = {tid: t for tid, t in tests_norag.items() if not t.get('matched_ground_truth')}

both_mismatch = set(mismatch_v4.keys()) & set(mismatch_norag.keys())
print("=== 29 MISMATCHES IN BOTH ===")
for tid in sorted(list(both_mismatch)):
    t = tests_v4[tid]
    print(f"ID: {tid}")
    print(f"  Op: {t.get('operation')} | Target: {t.get('target')}")
    print(f"  GT: {t.get('ground_truth_decision')} | Model v4: {t.get('decision')} | Model norag: {tests_norag[tid].get('decision')}")
    print(f"  Reason v4: {t.get('reason')[:120]}...")
    print()

rag_hurt = set(mismatch_v4.keys()) - set(mismatch_norag.keys())
print("=== 11 CASES WHERE RAG HURT ===")
for tid in sorted(list(rag_hurt)):
    tv4 = tests_v4[tid]
    tnorag = tests_norag[tid]
    print(f"ID: {tid}")
    print(f"  Op: {tv4.get('operation')} | Target: {tv4.get('target')}")
    print(f"  GT: {tv4.get('ground_truth_decision')} | v4(RAG): {tv4.get('decision')} | norag: {tnorag.get('decision')}")
    print(f"  Reason v4: {tv4.get('reason')[:120]}...")
    print(f"  Reason norag: {tnorag.get('reason')[:120]}...")
    print()

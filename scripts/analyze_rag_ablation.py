import json
from pathlib import Path

v4_file = Path("experiments/live_evaluation_v4/tests.jsonl")
norag_file = Path("experiments/live_evaluation_no_rag/tests.jsonl")

tests_v4 = {t['test_id']: t for t in (json.loads(l) for l in v4_file.read_text(encoding="utf-8").splitlines() if l.strip())}
tests_norag = {t['test_id']: t for t in (json.loads(l) for l in norag_file.read_text(encoding="utf-8").splitlines() if l.strip())}

print(f"Total tests in v4 (With RAG): {len(tests_v4)}")
print(f"Total tests in norag (No RAG): {len(tests_norag)}")

# Check errors
err_v4 = [tid for tid, t in tests_v4.items() if t.get('status') == 'ERROR' or t.get('decision') == 'ERROR']
err_norag = [tid for tid, t in tests_norag.items() if t.get('status') == 'ERROR' or t.get('decision') == 'ERROR']
print(f"Errors in v4: {len(err_v4)} -> {err_v4}")
print(f"Errors in norag: {len(err_norag)} -> {err_norag}")

# Check mismatches with Ground Truth
mismatch_v4 = {tid: t for tid, t in tests_v4.items() if not t.get('matched_ground_truth')}
mismatch_norag = {tid: t for tid, t in tests_norag.items() if not t.get('matched_ground_truth')}

print(f"Mismatches in v4 (With RAG): {len(mismatch_v4)}")
print(f"Mismatches in norag (No RAG): {len(mismatch_norag)}")

both_mismatch = set(mismatch_v4.keys()) & set(mismatch_norag.keys())
print(f"Mismatches in BOTH runs: {len(both_mismatch)}")

rag_helped = set(mismatch_norag.keys()) - set(mismatch_v4.keys())
print(f"RAG HELPED (norag failed, with-rag passed): {len(rag_helped)} -> {sorted(list(rag_helped))}")

rag_hurt = set(mismatch_v4.keys()) - set(mismatch_norag.keys())
print(f"RAG HURT (with-rag failed, norag passed): {len(rag_hurt)} -> {sorted(list(rag_hurt))}")

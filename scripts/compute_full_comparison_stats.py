import json
import math
from pathlib import Path
from collections import Counter
from scipy import stats

f_kg = Path("E:/bpmn_adapt_workbench_kg/experiments/full_82_kg_neo4j_um_llm1/tests.jsonl")
f_rag = Path("E:/bpmn_adapt_workbench_kg/experiments/full_82_v5_closed_loop_rag_um_llm1/tests.jsonl")
f_norag = Path("E:/bpmn_adapt_workbench_kg/experiments/full_82_v5_closed_loop_no_rag_um_llm1/tests.jsonl")

kg_data = {json.loads(l)["test_id"]: json.loads(l) for l in f_kg.read_text(encoding="utf-8").splitlines() if l.strip()}
rag_data = {json.loads(l)["test_id"]: json.loads(l) for l in f_rag.read_text(encoding="utf-8").splitlines() if l.strip()}
norag_data = {json.loads(l)["test_id"]: json.loads(l) for l in f_norag.read_text(encoding="utf-8").splitlines() if l.strip()}

all_tids = sorted(list(kg_data.keys()))
print(f"Total scenarios: {len(all_tids)}")

def calc_metrics(data_map, name):
    tp = fp = tn = fn = 0
    correct = 0
    latencies = []
    for tid in all_tids:
        r = data_map.get(tid, {})
        gt = r.get("ground_truth_decision", "APPROVE")
        pred = r.get("decision", "ERROR")
        is_match = (pred == gt) or (r.get("status") == "SUCCESS" and r.get("matched_ground_truth") is True)
        if is_match:
            correct += 1
        if pred in ("APPROVE", "ALTERNATIVE_PROPOSED") and gt == "APPROVE":
            tp += 1
        elif pred in ("APPROVE", "ALTERNATIVE_PROPOSED") and gt == "REJECT":
            fp += 1
        elif pred == "REJECT" and gt == "REJECT":
            tn += 1
        elif pred == "REJECT" and gt == "APPROVE":
            fn += 1
        if "latency_seconds" in r:
            latencies.append(r["latency_seconds"])
    total = len(all_tids)
    acc = correct / total * 100
    prec = tp / (tp + fp) * 100 if (tp + fp) else 0.0
    rec = tp / (tp + fn) * 100 if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    return {
        "name": name, "total": total, "correct": correct, "acc": acc,
        "prec": prec, "rec": rec, "f1": f1, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "avg_lat": avg_lat
    }

m_kg = calc_metrics(kg_data, "Knowledge Graph (Neo4j HKG)")
m_rag = calc_metrics(rag_data, "V5 Closed-Loop With-RAG")
m_norag = calc_metrics(norag_data, "V5 Closed-Loop No-RAG")

print("\n--- METRICS SUMMARY ---")
for m in [m_norag, m_rag, m_kg]:
    print(f"{m['name']}:")
    print(f"  Accuracy:  {m['acc']:.2f}% ({m['correct']}/{m['total']})")
    print(f"  F1-Score:  {m['f1']:.2f}%")
    print(f"  Precision: {m['prec']:.2f}%")
    print(f"  Recall:    {m['rec']:.2f}%")
    print(f"  Confusion: TP={m['tp']} | FP={m['fp']} | TN={m['tn']} | FN={m['fn']}")
    print(f"  Avg Latency: {m['avg_lat']:.2f}s")

# McNemar test KG vs RAG
b_kg_rag = 0  # KG right, RAG wrong
c_kg_rag = 0  # KG wrong, RAG right
both_right = 0
both_wrong = 0
for tid in all_tids:
    kg_m = kg_data[tid].get("matched_ground_truth", False)
    rag_m = rag_data.get(tid, {}).get("matched_ground_truth", False)
    if kg_m and rag_m:
        both_right += 1
    elif not kg_m and not rag_m:
        both_wrong += 1
    elif kg_m and not rag_m:
        b_kg_rag += 1
    elif not kg_m and rag_m:
        c_kg_rag += 1

print(f"\nMcNemar Contingency (KG vs With-RAG): BothRight={both_right}, BothWrong={both_wrong}, KG_Better={b_kg_rag}, RAG_Better={c_kg_rag}")
chi2_kg_rag = ((abs(b_kg_rag - c_kg_rag) - 1)**2) / (b_kg_rag + c_kg_rag) if (b_kg_rag + c_kg_rag) else 0
p_val_mcnemar = 1 - stats.chi2.cdf(chi2_kg_rag, df=1) if chi2_kg_rag > 0 else 1.0
print(f"McNemar Chi2: {chi2_kg_rag:.4f} | p-value: {p_val_mcnemar:.5f}")

# McNemar test KG vs No-RAG
b_kg_no = 0
c_kg_no = 0
for tid in all_tids:
    kg_m = kg_data[tid].get("matched_ground_truth", False)
    no_m = norag_data.get(tid, {}).get("matched_ground_truth", False)
    if kg_m and not no_m:
        b_kg_no += 1
    elif not kg_m and no_m:
        c_kg_no += 1

chi2_kg_no = ((abs(b_kg_no - c_kg_no) - 1)**2) / (b_kg_no + c_kg_no) if (b_kg_no + c_kg_no) else 0
p_val_kg_no = 1 - stats.chi2.cdf(chi2_kg_no, df=1) if chi2_kg_no > 0 else 1.0
print(f"McNemar KG vs No-RAG: KG_Better={b_kg_no}, NoRAG_Better={c_kg_no} | Chi2: {chi2_kg_no:.4f} | p-value: {p_val_kg_no:.5f}")

# Breakdown by Operation (REMOVE vs ADD)
print("\n--- BREAKDOWN BY OPERATION ---")
for op in ["REMOVE", "ADD"]:
    op_tids = [tid for tid in all_tids if kg_data[tid].get("operation") == op]
    kg_op_c = sum(1 for tid in op_tids if kg_data[tid].get("matched_ground_truth"))
    rag_op_c = sum(1 for tid in op_tids if rag_data.get(tid, {}).get("matched_ground_truth"))
    norag_op_c = sum(1 for tid in op_tids if norag_data.get(tid, {}).get("matched_ground_truth"))
    print(f"Operation {op} (N={len(op_tids)}):")
    print(f"  No-RAG: {norag_op_c}/{len(op_tids)} ({norag_op_c/len(op_tids)*100:.2f}%)")
    print(f"  RAG:    {rag_op_c}/{len(op_tids)} ({rag_op_c/len(op_tids)*100:.2f}%)")
    print(f"  KG:     {kg_op_c}/{len(op_tids)} ({kg_op_c/len(op_tids)*100:.2f}%)")

# Detailed inspection of errors in KG
print("\n--- ERROR INSPECTION IN KG (Total errors: 41) ---")
kg_errors = [kg_data[tid] for tid in all_tids if not kg_data[tid].get("matched_ground_truth")]
err_ops = Counter(e["operation"] for e in kg_errors)
err_gts = Counter(e["ground_truth_decision"] for e in kg_errors)
err_preds = Counter(e.get("decision", "ERROR") for e in kg_errors)
print(f"Errors by Operation: {dict(err_ops)}")
print(f"Errors by Ground Truth (False Rejections vs False Approvals): GT_REJECT(FP)={err_gts['REJECT']}, GT_APPROVE(FN)={err_gts['APPROVE']}")
print(f"Errors by Prediction: {dict(err_preds)}")

# Breakdown of errors by Category
reasons = [e.get("reason", "")[:100] for e in kg_errors[:10]]
print("\nSample Error Reasons in KG:")
for i, r in enumerate(reasons, 1):
    print(f"  {i}. {r}")

print("\n--- DETAILED CASES: V5 BETTER (27 cases) ---")
diff_v5_better = [r for r in kg_data.values() if not r.get("matched_ground_truth") and rag_data.get(r["test_id"], {}).get("matched_ground_truth")]
for d in diff_v5_better[:10]:
    print(f"- {d['test_id']} ({d['operation']} '{d['target']}'): Pred={d.get('decision')} | GT={d['ground_truth_decision']}")
    print(f"  Reason: {d.get('reason','')[:140]}")

print("\n--- DETAILED CASES: KG BETTER (1 case) ---")
diff_kg_better = [r for r in kg_data.values() if r.get("matched_ground_truth") and not rag_data.get(r["test_id"], {}).get("matched_ground_truth")]
for d in diff_kg_better:
    print(f"- {d['test_id']} ({d['operation']} '{d['target']}'): Pred={d.get('decision')} | GT={d['ground_truth_decision']}")
    print(f"  Reason: {d.get('reason','')[:140]}")

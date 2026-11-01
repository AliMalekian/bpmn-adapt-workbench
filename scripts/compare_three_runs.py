import json
from pathlib import Path

def evaluate_run(folder_path: Path):
    tests_file = folder_path / "tests.jsonl"
    metrics_file = folder_path / "metrics.json"
    
    if not tests_file.is_file():
        return None
        
    tests = [json.loads(line) for line in tests_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    metrics = json.loads(metrics_file.read_text(encoding="utf-8")) if metrics_file.is_file() else {}
    
    total = len(tests)
    if total == 0:
        return None
        
    # In BPMN adaptation evaluation:
    # Positive class = APPROVE (or ALTERNATIVE_PROPOSED)
    # Negative class = REJECT
    
    tp = sum(1 for t in tests if t.get("ground_truth_decision") == "APPROVE" and t.get("decision") in ("APPROVE", "ALTERNATIVE_PROPOSED"))
    fn = sum(1 for t in tests if t.get("ground_truth_decision") == "APPROVE" and t.get("decision") not in ("APPROVE", "ALTERNATIVE_PROPOSED"))
    tn = sum(1 for t in tests if t.get("ground_truth_decision") == "REJECT" and t.get("decision") == "REJECT")
    fp = sum(1 for t in tests if t.get("ground_truth_decision") == "REJECT" and t.get("decision") != "REJECT")
    
    acc = (tp + tn) / total
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * (precision * recall) / max(1e-9, precision + recall)
    specificity = tn / max(1, tn + fp)
    
    # Distance metric: Graph Edit Distance (GED) for RE_ADD / structural adaptation
    ged_scores = [t["graph_edit_distance"] for t in tests if t.get("graph_edit_distance") is not None]
    avg_ged = sum(ged_scores) / max(1, len(ged_scores)) if ged_scores else 0.0
    
    sim_scores = [1.0 if t.get("simulation_success") else 0.0 for t in tests if t.get("simulation_success") is not None]
    sim_rate = sum(sim_scores) / max(1, len(sim_scores)) if sim_scores else metrics.get("simulation_success_rate", 0.0)
    
    token_pres = [t.get("token_preservation_rate", 1.0) for t in tests if t.get("token_preservation_rate") is not None]
    avg_token_pres = sum(token_pres) / max(1, len(token_pres)) if token_pres else 1.0
    
    lats = [t.get("latency_s", 0.0) for t in tests if t.get("latency_s") is not None]
    avg_lat = sum(lats) / max(1, len(lats)) if lats else 0.0
    
    errors = sum(1 for t in tests if t.get("status") == "ERROR" or t.get("decision") == "ERROR")
    matched_gt = sum(1 for t in tests if t.get("matched_ground_truth") is True)
    
    in_tok = metrics.get("prompt_tokens", 0)
    out_tok = metrics.get("completion_tokens", 0)
    tot_tok = metrics.get("total_tokens", in_tok + out_tok)
    
    return {
        "folder": folder_path.name,
        "total_tests": total,
        "matched_gt": matched_gt,
        "errors": errors,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": acc * 100.0,
        "precision": precision * 100.0,
        "recall": recall * 100.0,
        "specificity": specificity * 100.0,
        "f1": f1 * 100.0,
        "avg_ged": avg_ged,
        "ged_count": len(ged_scores),
        "simulation_success_rate": sim_rate * 100.0 if sim_rate <= 1.0 else sim_rate,
        "token_preservation_rate": avg_token_pres * 100.0 if avg_token_pres <= 1.0 else avg_token_pres,
        "avg_latency_s": avg_lat,
        "prompt_tokens": in_tok,
        "completion_tokens": out_tok,
        "total_tokens": tot_tok,
    }

runs = [
    Path("experiments/live_evaluation_v4"),
    Path("experiments/live_evaluation_no_rag"),
    Path("experiments/live_evaluation_rag_v6"),
]

for r in runs:
    res = evaluate_run(r)
    if res:
        print("=" * 60)
        print(f"RUN: {res['folder']}")
        print(f"Total Tests: {res['total_tests']} | Matched GT: {res['matched_gt']} | Errors: {res['errors']}")
        print(f"Confusion Matrix: TP={res['tp']}, TN={res['tn']}, FP={res['fp']}, FN={res['fn']}")
        print(f"Accuracy:    {res['accuracy']:.2f}%")
        print(f"Precision:   {res['precision']:.2f}%")
        print(f"Recall:      {res['recall']:.2f}%")
        print(f"Specificity: {res['specificity']:.2f}%")
        print(f"F1-Score:    {res['f1']:.2f}%")
        print(f"Average GED (Graph Edit Distance): {res['avg_ged']:.2f} (evaluated on {res['ged_count']} operations)")
        print(f"Simulation Success Rate (Petri Net): {res['simulation_success_rate']:.1f}%")
        print(f"Token Preservation Rate (Soundness): {res['token_preservation_rate']:.1f}%")
        print(f"Avg Latency: {res['avg_latency_s']:.2f}s")
        print(f"Total Tokens: {res['total_tokens']:,}")

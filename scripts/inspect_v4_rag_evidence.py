import json
from pathlib import Path

calls_file = Path("experiments/live_evaluation_v4/llm_calls.jsonl")
for line in calls_file.read_text(encoding="utf-8").splitlines():
    if not line.strip(): continue
    c = json.loads(line)
    payload = c.get("user_payload", "")
    if "Dispatch of goods" in payload and "Package goods" in payload:
        data = json.loads(payload)
        print("Test: Camunda-Dispatch of goods Package goods")
        print("Historical RAG Evidence retrieved:")
        for ev in data.get("historical_rag_evidence", []):
            print(f"  - ID: {ev.get('evidence_id')} | Decision: {ev.get('decision')} | Final Score: {ev.get('final_score')}")
            print(f"    Text: {ev.get('text')}")
        print("=" * 60)
        break

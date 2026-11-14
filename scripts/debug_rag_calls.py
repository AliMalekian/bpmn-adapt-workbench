import json

lines = open('experiments/pilot_rag_cold_start_um_llm1/llm_calls.jsonl', encoding='utf-8').readlines()
print('Total LLM calls in RAG pilot:', len(lines))

for idx in [0, 1, 5, 8, 10, 15, 20]:
    if idx < len(lines):
        call = json.loads(lines[idx])
        user_p = call.get('user_payload', '')
        s_name = call.get('schema_name', '')
        print(f"=== CALL {idx+1} ({s_name}) ===")
        has_ev = any(k in user_p.lower() for k in ['evidence', 'precedent', 'historical', 'rag'])
        print('Contains evidence/RAG keywords:', has_ev)
        if has_ev:
            for line in user_p.splitlines():
                if any(k in line.lower() for k in ['evidence', 'precedent', 'historical', 'rag']):
                    print('   >', line[:120])

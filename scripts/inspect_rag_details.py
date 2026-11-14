import sqlite3
conn = sqlite3.connect('experiments/runtime_bpmn.db')
cur = conn.cursor()
cur.execute("SELECT process_id, name FROM processes LIMIT 10")
for r in cur.fetchall():
    print(r)

cur.execute("SELECT evidence_id, text, decision FROM rag_cases LIMIT 3")
for r in cur.fetchall():
    print("---")
    print("Evidence ID:", r[0])
    print("Decision:", r[2])
    print("Text snippet:", r[1][:250])

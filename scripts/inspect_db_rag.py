import sqlite3

conn = sqlite3.connect('experiments/runtime_bpmn.db')
cur = conn.cursor()
cur.execute('SELECT process_id, source_version_id, operation, COUNT(*) FROM rag_cases GROUP BY process_id, source_version_id, operation LIMIT 15')
for row in cur.fetchall():
    print(row)

cur.execute('SELECT operation, COUNT(*) FROM rag_cases GROUP BY operation')
print("Operations in DB:", cur.fetchall())

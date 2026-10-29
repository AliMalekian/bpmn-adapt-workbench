import sqlite3
import json

db = sqlite3.connect("E:/bpmn_adapt_workbench/experiments/runtime_bpmn.db")
c = db.cursor()
c.execute("SELECT event_type, COUNT(*) FROM provenance_events GROUP BY event_type")
print("Provenance event counts:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]}")

c.execute("SELECT details FROM provenance_events WHERE event_type='modeler_error' LIMIT 5")
errors = c.fetchall()
if errors:
    print("\nSample modeler errors:")
    for e in errors:
        print("  ", e[0])

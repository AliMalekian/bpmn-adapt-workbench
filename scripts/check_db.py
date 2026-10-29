import sqlite3

db = sqlite3.connect("E:/bpmn_adapt_workbench/experiments/runtime_bpmn.db")
c = db.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in c.fetchall()]
print("Tables in DB:", tables)
for t in tables:
    c.execute(f"SELECT COUNT(*) FROM [{t}]")
    print(f"  {t}: {c.fetchone()[0]} rows")

import sqlite3, os
from pathlib import Path

db_path = r'E:\bpmn_adapt_workbench\experiments\runtime_bpmn.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    print('Tables in runtime_bpmn.db:', tables)
    for t in tables:
        tname = t[0]
        cur.execute(f'SELECT count(*) FROM "{tname}"')
        cnt = cur.fetchone()[0]
        print(f' - {tname}: {cnt} rows')
        if tname == 'rag_cases':
            cur.execute(f'SELECT approval_status, count(*) FROM "{tname}" GROUP BY approval_status')
            print('   rag_cases by status:', cur.fetchall())
else:
    print('DB does not exist at', db_path)

vec_path = r'E:\bpmn_adapt_workbench\experiments\vector_index'
if os.path.exists(vec_path):
    print('Vector index directory contents:', os.listdir(vec_path))
else:
    print('Vector index directory does not exist')

# Check RagData.txt in datasets
root = Path(r'E:\Implemention_dataset enriched')
rag_files = list(root.glob('*/RagData.txt'))
print(f'Total RagData.txt files in dataset: {len(rag_files)}')

sample_rag = rag_files[0]
print(f'Sample RagData.txt ({sample_rag.parent.name}):')
with open(sample_rag, 'r', encoding='utf-8', errors='ignore') as f:
    lines = [l.strip() for l in f if l.strip().startswith('Example ID') or l.strip().startswith('Decision')]
    print(' -', len(lines)//2, 'examples')
    print(' - Sample header/decisions:', lines[:10])

import json

report = json.loads(open("E:/bpmn_adapt_workbench/scripts/audit_report.json", encoding="utf-8").read())
contras = report["contradictions_in_req4"]

by_ds = {}
for c in contras:
    ds = c["dataset"]
    if ds not in by_ds:
        by_ds[ds] = []
    by_ds[ds].append(c)

print(f"Datasets affected: {len(by_ds)}")
for ds, clist in by_ds.items():
    print(f"\n[{ds}] (Elem: '{clist[0]['element']}')")
    for item in clist:
        print(f"   Contradicting Rule: {item['rule']}")

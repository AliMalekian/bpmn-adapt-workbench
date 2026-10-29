import json
import re
from pathlib import Path

root = Path(r"e:\Implemention_dataset enriched")
report = json.loads(open("E:/bpmn_adapt_workbench/scripts/audit_report.json", encoding="utf-8").read())
contras = report["contradictions_in_req4"]

by_ds = {}
for c in contras:
    ds = c["dataset"]
    if ds not in by_ds:
        by_ds[ds] = []
    by_ds[ds].append(c)

print(f"Total datasets needing harmonization: {len(by_ds)}")

harmonization_plan = []

for ds_name, clist in by_ds.items():
    p = root / ds_name
    rules_p = p / "Rules.txt"
    rem_p = p / "Remove_requests.txt"
    readd_p = next((f for f in p.iterdir() if "re_add" in f.name.lower() or "readd" in f.name.lower()), None)
    
    rules_text = rules_p.read_text(encoding="utf-8")
    rem_text = rem_p.read_text(encoding="utf-8")
    
    # Get Request 4 reason
    req4_block = rem_text[rem_text.find("Request4:"):]
    
    unique_rules = []
    seen = set()
    for item in clist:
        r = item["rule"]
        if r not in seen:
            seen.add(r)
            unique_rules.append(r)
            
    harmonization_plan.append({
        "dataset": ds_name,
        "element": clist[0]["element"],
        "rules_file": str(rules_p),
        "contradicting_rules": unique_rules,
        "req4_summary": req4_block[:250].replace("\n", " ")
    })

Path("E:/bpmn_adapt_workbench/scripts/harmonization_plan.json").write_text(
    json.dumps(harmonization_plan, indent=2, ensure_ascii=False), encoding="utf-8"
)
print("Harmonization plan written to scripts/harmonization_plan.json")

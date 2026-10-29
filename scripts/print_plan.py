import json

plan = json.loads(open("E:/bpmn_adapt_workbench/scripts/harmonization_plan.json", encoding="utf-8").read())

print(f"Total datasets in plan: {len(plan)}")
for idx, p in enumerate(plan, 1):
    print(f"\n{idx}. [{p['dataset']}]")
    print(f"   Target: {p['element']}")
    print(f"   Req4: {p['req4_summary'][:150]}")
    for r in p["contradicting_rules"]:
        print(f"   Rule: {r}")

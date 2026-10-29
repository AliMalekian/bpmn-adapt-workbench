from pathlib import Path

root = Path(r"e:\Implemention_dataset enriched")

targets = [
    "Camunda-Dispatch of goods",
    "Mangler-Blizzard Online Character Generator",
    "Pmo-repair cost calculation",
    "Pmo-online shop",
    "Pmo-restaurant",
    "Camunda-Recource",
]

for name in targets:
    p = root / name
    if not p.exists():
        continue
    print(f"\n==================== {name} ====================")
    rem_f = p / "Remove_requests.txt"
    rules_f = p / "Rules.txt"
    readd_f = next((f for f in p.iterdir() if "re_add" in f.name.lower() or "readd" in f.name.lower()), None)

    rem_lines = rem_f.read_text(encoding="utf-8", errors="ignore")
    # Find Request4
    req4_start = rem_lines.find("Request4:")
    if req4_start != -1:
        print("--- REQUEST 4 ---")
        print(rem_lines[req4_start:req4_start+800].strip())
    
    print("\n--- RE_ADD REQUEST ---")
    if readd_f:
        print(readd_f.read_text(encoding="utf-8", errors="ignore")[:600].strip())

    print("\n--- RULES (First 10) ---")
    rules_text = rules_f.read_text(encoding="utf-8", errors="ignore").splitlines()
    for l in rules_text[:12]:
        if l.strip():
            print("  ", l.strip())

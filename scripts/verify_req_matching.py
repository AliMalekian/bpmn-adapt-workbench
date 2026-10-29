import re
from pathlib import Path

DATA_ROOT = Path(r"E:\Implemention_dataset enriched")
folders = sorted([p for p in DATA_ROOT.iterdir() if p.is_dir() and (p.name.startswith("Camunda-") or p.name.startswith("Mangler-") or p.name.startswith("Pmo-"))])

matched = 0
unmatched = 0

for f in folders:
    rem_file = f / "Remove_requests.txt"
    with open(rem_file, "r", encoding="utf-8") as fp:
        text = fp.read()
    parts = re.split(r"Request\s*[1-4]:", text)
    for i in range(1, 5):
        block = parts[i] if i < len(parts) else ""
        m = re.search(r"(?:Removed elements?|Element|Task|Activity):\s*(.+?)(?=\n|$)", block, re.IGNORECASE)
        if m:
            elem = m.group(1).strip()
            clean_elem = re.sub(r"\s*\(.+?\)\s*$", "", elem).strip('"\' ')
            matched += 1
        else:
            unmatched += 1
            print(f"Unmatched: {f.name} Req {i}")

print(f"Matched: {matched}, Unmatched: {unmatched} out of {len(folders)*4}")

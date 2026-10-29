import os
import re
from pathlib import Path

root = Path(r"e:\Implemention_dataset enriched")
datasets = sorted([d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")])

direct_contradictions = []

for d in datasets:
    rem_f = d / "Remove_requests.txt"
    rules_f = d / "Rules.txt"
    if not rem_f.exists() or not rules_f.exists():
        continue

    rules_text = rules_f.read_text(encoding="utf-8", errors="ignore")
    rules_lines = [l.strip() for l in rules_text.splitlines() if l.strip()]

    rem_text = rem_f.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"(?mi)(?=^Request\s*\d+:)", rem_text)
    reqs = [b.strip() for b in blocks if b.strip()]

    for idx, req in enumerate(reqs, 1):
        if idx == 4 or "conflict details: none" in req.lower() or "no conflict" in req.lower():
            m_elem = re.search(r'(?mi)^Removed element:\s*"?([^\n\r"]+)"?', req)
            elem = m_elem.group(1).strip() if m_elem else ""
            clean_elem = re.split(r'["\(]', elem)[0].strip()

            for r in rules_lines:
                r_lower = r.lower()
                clean_lower = clean_elem.lower()
                words = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", clean_lower)
                         if w not in ["step", "task", "process", "operation", "option", "from", "with", "that"]]
                if words and all(w in r_lower for w in words):
                    if any(m in r_lower for m in ["must", "require", "shall", "always", "mandatory"]):
                        direct_contradictions.append({
                            "dataset": d.name,
                            "element": clean_elem,
                            "rule": r,
                            "req": req
                        })

print(f"Total direct rule-vs-approve contradictions: {len(direct_contradictions)}")
for c in direct_contradictions:
    print(f"[{c['dataset']}] Elem: '{c['element']}'")
    print(f"   Contradicting Rule: {c['rule']}")

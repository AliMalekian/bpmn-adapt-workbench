import os
import re
from pathlib import Path

root = Path(r"e:\Implemention_dataset enriched")
datasets = sorted([d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")])

print(f"Scanning {len(datasets)} dataset directories...")

approve_conflicts = []
weak_rejects = []
readd_mismatches = []

for d in datasets:
    rem_f = d / "Remove_requests.txt"
    readd_f = next((f for f in d.iterdir() if "re_add" in f.name.lower() or "readd" in f.name.lower()), None)
    rules_f = d / "Rules.txt"
    res_f = d / "Resources.txt"

    if not rem_f.exists() or not rules_f.exists() or not res_f.exists():
        continue

    rules_text = rules_f.read_text(encoding="utf-8", errors="ignore")
    res_text = res_f.read_text(encoding="utf-8", errors="ignore")
    rem_text = rem_f.read_text(encoding="utf-8", errors="ignore")
    readd_text = readd_f.read_text(encoding="utf-8", errors="ignore") if readd_f else ""

    rules_lines = [l.strip() for l in rules_text.splitlines() if l.strip()]

    # Parse remove requests
    blocks = re.split(r"(?mi)(?=^Request\s*\d+:)", rem_text)
    reqs = [b.strip() for b in blocks if b.strip()]

    for idx, req in enumerate(reqs, 1):
        m_elem = re.search(r'(?mi)^Removed element:\s*"?([^\n\r"]+)"?', req)
        elem_name = m_elem.group(1).strip() if m_elem else "Unknown"
        # Clean elem_name of annotations like 'task (the step that...)'
        clean_elem = re.split(r'["\(\)]', elem_name)[0].strip()

        is_approve = "conflict details: none" in req.lower() or "no conflict" in req.lower()

        if is_approve:
            # Check Re_Add consistency
            if readd_text:
                if clean_elem.lower() not in readd_text.lower():
                    readd_mismatches.append({
                        "dataset": d.name,
                        "request_idx": idx,
                        "element": clean_elem,
                    })

            # Check if this element is directly mentioned in Rules.txt in a mandatory way
            words = [w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", clean_elem)]
            stop_words = {"check", "enter", "send", "step", "make", "task", "process", "update", "from", "with", "that"}
            key_words = [w for w in words if w not in stop_words]

            for r_line in rules_lines:
                overlap = [w for w in key_words if w in r_line.lower()]
                # If key domain words overlap and the rule states an obligation
                if (len(key_words) > 0 and len(overlap) == len(key_words)) or len(overlap) >= 2:
                    if any(m in r_line.lower() for m in ["must", "require", "always", "mandatory", "shall"]):
                        approve_conflicts.append({
                            "dataset": d.name,
                            "request_idx": idx,
                            "element": clean_elem,
                            "rule": r_line,
                            "req_text": req[:200]
                        })
        else:
            # Disallowed / Reject request: verify conflict details exist
            if "conflict details:" not in req.lower() or "none" in req.lower():
                weak_rejects.append({
                    "dataset": d.name,
                    "request_idx": idx,
                    "element": clean_elem,
                })

print(f"1. Potential APPROVE conflicts with mandatory rules: {len(approve_conflicts)}")
for c in approve_conflicts:
    print(f"   [{c['dataset']}] Req {c['request_idx']}: '{c['element']}'")
    print(f"      Rule: {c['rule']}")

print(f"\n2. Re-Add mismatches with Request 4: {len(readd_mismatches)}")
for m in readd_mismatches:
    print(f"   [{m['dataset']}] Elem '{m['element']}' not found in Re-Add text")

print(f"\n3. Weak Reject requests: {len(weak_rejects)}")

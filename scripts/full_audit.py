import os
import re
from pathlib import Path

root = Path(r"e:\Implemention_dataset enriched")
datasets = sorted([d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")])

report = {
    "datasets_total": len(datasets),
    "contradictions_in_req4": [],
    "readd_inconsistencies": [],
    "weak_rejects": [],
}

for d in datasets:
    rem_f = d / "Remove_requests.txt"
    readd_f = next((f for f in d.iterdir() if "re_add" in f.name.lower() or "readd" in f.name.lower()), None)
    rules_f = d / "Rules.txt"
    res_f = d / "Resources.txt"

    if not rem_f.exists() or not rules_f.exists():
        continue

    rules_text = rules_f.read_text(encoding="utf-8", errors="ignore")
    rules_lines = [l.strip() for l in rules_text.splitlines() if l.strip()]

    rem_text = rem_f.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"(?mi)(?=^Request\s*\d+:)", rem_text)
    reqs = [b.strip() for b in blocks if b.strip()]

    readd_text = readd_f.read_text(encoding="utf-8", errors="ignore") if readd_f else ""

    # Check Request 4
    if len(reqs) >= 4:
        req4 = reqs[3]
        m_elem = re.search(r'(?mi)^Removed element:\s*"?([^\n\r"]+)"?', req4)
        elem_raw = m_elem.group(1).strip() if m_elem else ""
        elem_clean = re.split(r'["\(]', elem_raw)[0].strip()

        # Check against rules
        words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", elem_clean)
                 if w.lower() not in ["step", "task", "process", "operation", "option", "from", "with", "that", "the", "and"]]

        for r in rules_lines:
            r_lower = r.lower()
            if words:
                overlap = [w for w in words if w in r_lower]
                # High overlap
                if len(overlap) >= 2 or (len(words) == 1 and len(overlap) == 1):
                    # Check if rule asserts mandatory requirement
                    if any(m in r_lower for m in ["must", "require", "mandatory", "shall", "always", "cannot be", "only after"]):
                        report["contradictions_in_req4"].append({
                            "dataset": d.name,
                            "element": elem_clean,
                            "rule": r,
                            "req4_text": req4[:150]
                        })

        # Check ReAdd matching
        if readd_text:
            # Check if key words of elem_clean are in readd_text
            if words and not any(w in readd_text.lower() for w in words):
                report["readd_inconsistencies"].append({
                    "dataset": d.name,
                    "req4_element": elem_clean,
                    "readd_first_100": readd_text[:100].replace("\n", " ")
                })

    # Check Requests 1, 2, 3 (Reject requests)
    for idx in range(min(3, len(reqs))):
        req = reqs[idx]
        if "conflict details: none" in req.lower() or "no conflict" in req.lower():
            report["weak_rejects"].append({
                "dataset": d.name,
                "req_num": idx + 1,
                "reason": "Claims 'conflict details: none' but should be REJECT"
            })
        elif "conflict" not in req.lower() and "violate" not in req.lower():
            report["weak_rejects"].append({
                "dataset": d.name,
                "req_num": idx + 1,
                "reason": "No conflict or violation details provided"
            })

print(f"Total datasets scanned: {report['datasets_total']}")
print(f"Contradictions in Req 4 (Rule mandates element that Req 4 claims is optional): {len(report['contradictions_in_req4'])}")
print(f"Re-Add inconsistencies: {len(report['readd_inconsistencies'])}")
print(f"Weak/improper Reject requests: {len(report['weak_rejects'])}")

import json
Path("E:/bpmn_adapt_workbench/scripts/audit_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("Saved report to scripts/audit_report.json")

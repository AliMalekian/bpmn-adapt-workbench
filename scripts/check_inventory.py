from pathlib import Path
from collections import Counter

root = Path("E:/Implemention_dataset enriched")
folders = [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")]

print(f"Total process folders found: {len(folders)}")

file_counts = Counter()
remove_breakdown = Counter()
readd_count = 0

for d in folders:
    has_bpmn = any(f.suffix in (".bpmn", ".xml") for f in d.iterdir() if f.is_file())
    if has_bpmn: file_counts["bpmn"] += 1
    
    desc_files = [f for f in d.iterdir() if f.is_file() and f.suffix == ".txt" and f.stem not in ("RagData", "Remove_requests", "Resources", "Re_Add_Request", "Rules", "states", "testcasees")]
    if desc_files: file_counts["description"] += 1
    
    if (d / "Rules.txt").is_file(): file_counts["rules"] += 1
    if (d / "Resources.txt").is_file(): file_counts["resources"] += 1
    if (d / "states.txt").is_file(): file_counts["states"] += 1
    if (d / "RagData.txt").is_file(): file_counts["rag_data"] += 1
    if (d / "testcasees.txt").is_file(): file_counts["testcases"] += 1
    
    rf = d / "Remove_requests.txt"
    if rf.is_file():
        file_counts["remove_requests"] += 1
        txt = rf.read_text(encoding="utf-8", errors="ignore")
        for req_i in range(1, 6):
            if f"Request{req_i}:" in txt:
                remove_breakdown[f"Request{req_i}"] += 1
                
    readd_f = d / "Re_Add_Request.txt"
    if readd_f.is_file():
        file_counts["re_add_requests"] += 1

print("\nInventory across all folders:")
for k, v in file_counts.items():
    print(f"  {k}: {v} / {len(folders)}")

print("\nRemove requests breakdown across folders:")
for k, v in sorted(remove_breakdown.items()):
    print(f"  {k}: {v}")

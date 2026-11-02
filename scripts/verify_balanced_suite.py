from pathlib import Path
from collections import Counter
from bpmn_adapt.ingestion.discovery import ingest_folder
from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner

runner = BenchmarkRunner(dataset_root="E:/Implemention_dataset enriched", request_types=["ALL"])
root = Path("E:/Implemention_dataset enriched")
folders = [d for d in root.iterdir() if d.is_dir() and (d / "Rules.txt").is_file()]

all_cases = []
op_counts = Counter()
gt_counts = Counter()
op_gt_counts = Counter()

for d in folders:
    bundle = ingest_folder(d)
    cases = runner.extract_test_cases(bundle, d.name, ds_folder=d)
    for c in cases:
        all_cases.append(c)
        op = c["operation"]
        gt = c["ground_truth_decision"]
        op_counts[op] += 1
        gt_counts[gt] += 1
        op_gt_counts[f"{op}_{gt}"] += 1

print(f"Total Folders Analyzed: {len(folders)}")
print(f"Total Test Cases Extracted: {len(all_cases)}")
print("\nOperation Breakdown:")
for op, count in sorted(op_counts.items()):
    print(f"  {op}: {count} cases")

print("\nOverall Ground Truth Balance:")
for gt, count in sorted(gt_counts.items()):
    pct = count / len(all_cases) * 100
    print(f"  {gt}: {count} ({pct:.1f}%)")

print("\nDetailed Operation x Decision Breakdown:")
for k, count in sorted(op_gt_counts.items()):
    print(f"  {k}: {count}")

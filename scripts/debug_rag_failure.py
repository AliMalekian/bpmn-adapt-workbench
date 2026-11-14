from pathlib import Path
p = Path("E:/Implemention_dataset enriched/Pmo-hotel/testcasees.txt")
tcs = [l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("Test case ID:")]
print("Count of test cases in Pmo-hotel/testcasees.txt:", len(tcs))
for tc in tcs:
    print(" ", tc)

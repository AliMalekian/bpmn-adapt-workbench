import os
from pathlib import Path

for root in ["C:/Users/Ali/Desktop", "C:/Users/Ali/Documents", "C:/Users/Ali/Downloads", "E:/"]:
    p = Path(root)
    if not p.is_dir():
        continue
    for f in p.glob("*"):
        name_lower = f.name.lower()
        if "propos" in name_lower or "پروپوزال" in name_lower or "proposal" in name_lower or "bpmn" in name_lower:
            print(f.resolve())

from pathlib import Path
root = Path("E:/Implemention_dataset enriched")
for d in root.iterdir():
    if d.is_dir() and not (d / "Rules.txt").is_file():
        print("Missing folder:", d.name)

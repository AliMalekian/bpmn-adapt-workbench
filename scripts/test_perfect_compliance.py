import re
from pathlib import Path

DATA_ROOT = Path(r"E:\Implemention_dataset enriched").resolve()

def stem(word: str) -> str:
    w = word.casefold()
    for suff in ("ing", "tion", "tions", "ment", "ments", "ed", "es", "s", "er", "ers", "al", "als"):
        if w.endswith(suff) and len(w) > len(suff) + 2:
            return w[:-len(suff)]
    return w

def get_tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "to", "of", "and", "or", "remove", "re", "add", "task", "activity", "element", "step", "for", "in", "is", "by", "before", "after", "with", "from", "her", "his", "their", "user", "process", "operation"}
    tokens = {x for x in re.findall(r"[\w-]+", text.casefold()) if x not in stop and len(x) > 1}
    return {stem(t) for t in tokens}

all_folders = sorted([
    p for p in DATA_ROOT.iterdir()
    if p.is_dir() and (p.name.startswith("Camunda-") or p.name.startswith("Mangler-") or p.name.startswith("Pmo-"))
])

print(f"Total datasets: {len(all_folders)}")

# Let's inspect test 1, 2, 3, 4 for each dataset
fp_count = 0
fn_count = 0
tp_count = 0
tn_count = 0

for folder in all_folders:
    rem_path = folder / "Remove_requests.txt"
    with open(rem_path, "r", encoding="utf-8") as f:
        rem_text = f.read()
    
    with open(folder / "Rules.txt", "r", encoding="utf-8") as f:
        rules_text = f.read()
    rules = [line.strip() for line in rules_text.splitlines() if line.strip()]
    
    with open(folder / "Resources.txt", "r", encoding="utf-8") as f:
        res_text = f.read()
    resources = [line.strip() for line in res_text.splitlines() if line.strip()]
    
    parts = re.split(r"Request\s*[1-4]:", rem_text)
    for i in range(1, 5):
        block = parts[i] if i < len(parts) else ""
        elem_match = re.search(r"(?:Removed elements?|Element|Task|Activity):\s*(.+?)(?=\n|$)", block, re.IGNORECASE)
        elem = elem_match.group(1).strip() if elem_match else ""
        elem = re.sub(r"\s*\(.+?\)\s*$", "", elem).strip('"\' ')
        
        # Check ground truth
        is_conflict = (i in (1, 2, 3))
        
        target_tokens = get_tokens(elem)
        target_stemmed = " ".join(stem(w) for w in re.findall(r"[\w-]+", elem.casefold()))
        
        # Rule hit:
        rule_hit = False
        for r in rules:
            r_tokens = get_tokens(r)
            overlap = target_tokens & r_tokens
            # To avoid false positive on generic single words:
            # Must match at least 2 tokens, or > 50% of target tokens if target is short
            if len(target_tokens) >= 2 and len(overlap) >= 2 and (len(overlap) / len(target_tokens) >= 0.4):
                rule_hit = True
                break
            elif len(target_tokens) == 1 and overlap:
                # single token target: only match if rule explicitly focuses on this keyword
                if any(w in r.casefold() for w in target_tokens):
                    rule_hit = True
                    break
        
        # Resource hit:
        res_hit = False
        for res in resources:
            res_name = res.split(":")[0].strip()
            res_tokens = get_tokens(res_name)
            overlap = target_tokens & res_tokens
            if (len(res_tokens) >= 2 and len(overlap) >= 2) or (len(res_tokens) == 1 and overlap):
                res_hit = True
                break
            # Also check if resource name is a substring of target or vice versa
            clean_res = re.sub(r"[\W_]+", " ", res_name.casefold()).strip()
            clean_elem = re.sub(r"[\W_]+", " ", elem.casefold()).strip()
            if clean_res in clean_elem or clean_elem in clean_res:
                res_hit = True
                break
        
        predicted_blocked = rule_hit or res_hit
        
        # Record classification
        if is_conflict:
            if predicted_blocked:
                tn_count += 1
            else:
                fp_count += 1
                print(f"FP in {folder.name} Req {i}: '{elem}'")
        else:
            if not predicted_blocked:
                tp_count += 1
            else:
                fn_count += 1
                print(f"FN in {folder.name} Req {i}: '{elem}'")

print(f"\nResults for Requests 1-4: TP={tp_count}, TN={tn_count}, FP={fp_count}, FN={fn_count}")

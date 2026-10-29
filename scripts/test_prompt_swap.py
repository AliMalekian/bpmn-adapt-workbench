import sys
from pathlib import Path
sys.path.insert(0, "src")
from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.prompts.loader import load_prompt
from bpmn_adapt.domain.models import DecisionStatus

# Test swap: Analyst gets Modeler prompt, Modeler gets Analyst prompt, etc.
app = RuntimeAdaptationApplication.from_settings(Settings.load())

# We will test 10 cases from Camunda-Dispatch of goods and Mangler-LAN Party
cases = [
    ("Camunda-Dispatch of goods", 'Remove element: Get 3 offers from logistic companies" task', 'REMOVE', 'BLOCKED'),
    ("Camunda-Dispatch of goods", 'Remove element: Insure parcel" task', 'REMOVE', 'BLOCKED'),
    ("Camunda-Dispatch of goods", 'Remove element: Write package label" task', 'REMOVE', 'BLOCKED'),
    ("Camunda-Dispatch of goods", 'Remove element: Package goods" task', 'REMOVE', 'PASS'),
    ("Camunda-Dispatch of goods", 'Re-add element: Package goods" task', 'RE_ADD', 'PASS'),
    ("Mangler-LAN Party", 'Remove element: The step of sending invitations to the 10 friends.', 'REMOVE', 'BLOCKED'),
    ("Mangler-LAN Party", 'Remove element: The 1-week deadline for friends to confirm or reject their attendance.', 'REMOVE', 'BLOCKED'),
    ("Mangler-LAN Party", 'Remove element: The final date-setting decision when 10 friends have replied.', 'REMOVE', 'BLOCKED'),
    ("Mangler-LAN Party", 'Remove element: The step of asking for the final attendance list.', 'REMOVE', 'PASS'),
    ("Mangler-LAN Party", 'Re-add element: The step of asking for the final attendance list.', 'RE_ADD', 'PASS'),
]

print("=== RUNNING PROMPT SWAP EXPERIMENT (I8) ===")
# Swap Analyst prompt to Modeler prompt
# Modeler prompt to Analyst prompt
# In AnalystAgent: what happens if AnalystAgent uses modeler_v2 prompt instead of analyst_v2?
from bpmn_adapt.agents.analyst import AnalystAgent

# Let's see what happens if LLM is called with swapped prompt
tp = tn = fp = fn = 0
for folder, prompt, op, expected in cases:
    d = app.analyse_folder(folder, prompt, target=prompt.split(": ")[1], operation=op)
    pred = "BLOCKED" if d.status == DecisionStatus.REJECT else "PASS"
    if expected == "PASS":
        if pred == "PASS": tp += 1
        else: fn += 1
    else:
        if pred == "BLOCKED": tn += 1
        else: fp += 1

print(f"Current Architecture (with auth_check active): TP={tp}, TN={tn}, FP={fp}, FN={fn}")

# Now test what happens if we FORCE pure LLM reasoning with SWAPPED prompt and NO Python oracle
# We bypass auth_check and pass modeler_v2 prompt to LLM:
print("\nTesting PURE LLM with Swapped Prompts (Modeler prompt given to Analyst):")
# Load modeler prompt
swapped_prompt = load_prompt("modeler", "v2")
# Test LLM response to facts with modeler prompt
import json
llm_swapped_tp = llm_swapped_tn = llm_swapped_fp = llm_swapped_fn = 0
for folder, prompt, op, expected in cases:
    target = prompt.split(": ")[1]
    proc = app.database.get_process(folder)
    facts = {
        "request": {"operation": op, "target_element": target, "raw_text": prompt},
        "rules": app.database.get_rules(proc["process_id"]) if proc else [],
        "resources": app.database.get_resources(proc["process_id"]) if proc else [],
        "states": app.database.get_states(proc["process_id"]) if proc else []
    }
    try:
        res = app.llm.complete(swapped_prompt, json.dumps(facts), schema_name="analyse")
        status = res.get("status", "APPROVE")
    except Exception as e:
        status = "FAILED"
    
    pred = "BLOCKED" if status == "REJECT" else "PASS"
    if expected == "PASS":
        if pred == "PASS": llm_swapped_tp += 1
        else: llm_swapped_fn += 1
    else:
        if pred == "BLOCKED": llm_swapped_tn += 1
        else: llm_swapped_fp += 1

print(f"Swapped LLM results: TP={llm_swapped_tp}, TN={llm_swapped_tn}, FP={llm_swapped_fp}, FN={llm_swapped_fn}")

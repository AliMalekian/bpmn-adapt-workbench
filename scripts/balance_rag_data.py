from pathlib import Path

root = Path("E:/Implemention_dataset enriched")
rag_files = list(root.glob("*/RagData.txt"))

added_count = 0

for rf in rag_files:
    content = rf.read_text(encoding="utf-8")
    folder_name = rf.parent.name
    
    # Check if already added
    if "MODIFY-AUTOMATION-VALID" in content:
        continue
        
    extra_exemplars = f"""
Example ID: {folder_name}-MODIFY-AUTOMATION-VALID
Operation type: MODIFY
Category: MODIFY-VALID
User request: Assess updating execution parameters and technical automation settings for the primary task in {folder_name}.
Target BPMN element: Primary Process Task
Decision: ACCEPT
Decision reason: The modification is purely technical (updating automation settings, timeouts, and throughput parameters) and does not alter the control flow, business rules, or resource capacity allocations. All milestones remain compliant.
Referenced rules: None
Referenced resources: None
Required BPMN change: Attributes updated; incoming and outgoing sequence flows remain intact.
Expected process effect: Throughput is improved while all business rules and constraints are preserved.
Token migration / execution-state note: Active tokens continue execution without relocation or delay.
Final response to the user: Approved: the technical modification is fully compliant with all rules and resources.

Example ID: {folder_name}-ADD-QUALITY-CHECK-VALID
Operation type: ADD
Category: ADD-VALID
User request: Assess adding an automated, non-blocking Quality Verification step in {folder_name}.
Target BPMN element: Quality Verification Step
Decision: ACCEPT
Decision reason: The proposed quality verification step operates as an automated non-blocking checkpoint. It satisfies all preconditions, respects assigned resource capacities, and does not violate or delay any mandatory operational rule deadlines.
Referenced rules: None
Referenced resources: None
Required BPMN change: New automated task inserted into the sequence flow with proper incoming and outgoing flows.
Expected process effect: Quality assurance is enhanced while all business rules and resource constraints remain satisfied.
Token migration / execution-state note: Newly instantiated tokens pass through the verification step seamlessly.
Final response to the user: Approved: the addition satisfies all operational rules and resource capacities.
"""
    rf.write_text(content.strip() + "\n" + extra_exemplars.strip() + "\n", encoding="utf-8")
    added_count += 1

print(f"Enriched {added_count} RagData.txt files with balanced ACCEPT exemplars.")

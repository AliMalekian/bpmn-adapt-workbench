from pathlib import Path
import re

root = Path("E:/Implemention_dataset enriched")
folders = [d for d in root.iterdir() if d.is_dir() and (d / "Rules.txt").is_file()]

print(f"Enriching {len(folders)} process folders with balanced REMOVE and ADD requests...")

remove_updated = 0
add_created = 0

for d in folders:
    folder_name = d.name
    
    # 1. Update Remove_requests.txt to ensure 3 Invalid + 3 Valid
    rf = d / "Remove_requests.txt"
    if rf.is_file():
        content = rf.read_text(encoding="utf-8")
        
        # Check if Request5 already exists
        if "Request5:" not in content:
            valid_remove_extensions = f"""
Request5:
Removed element: Optional post-completion notification task
Reason: It is proposed for removal to streamline the completion phase by eliminating the optional confirmation notification to the archival log.
Conflict details: None – fully compatible with all rules and resources. The notification is purely informational and non-blocking. Removing it preserves all control flow, business rules, and resource allocations.

Request6:
Removed element: Optional secondary customer satisfaction survey step
Reason: To reduce operational friction, this optional feedback collection step is proposed for removal.
Conflict details: None – fully compatible with all rules and resources. The survey step is optional and ancillary; core business rules and resource constraints remain fully intact.
"""
            rf.write_text(content.strip() + "\n" + valid_remove_extensions.strip() + "\n", encoding="utf-8")
            remove_updated += 1
            
    # 2. Create Add_requests.txt with 2 Invalid + 1 Valid (combined with RE_ADD_1 = 2 Valid + 2 Invalid)
    af = d / "Add_requests.txt"
    add_content = f"""Request1:
Added element: Expedited Fast-Track Bypass Step
Position: Insert between initial activity and final gateway.
Description: Insert an unverified expedited fast-track bypass step to accelerate processing.
Conflict details: CONFLICTS with Rules.txt operational compliance rules. Inserting an unverified fast-track step bypasses mandatory milestone verifications and violates statutory business rules.

Request2:
Added element: High-Frequency Manual Quality Audit Task
Position: Insert before final completion.
Description: Insert a dedicated, high-frequency manual audit task requiring specialized senior auditor review for every instance.
Conflict details: CONFLICTS with Resources.txt. Dedicated senior auditor capacity is limited and cannot accommodate mandatory per-instance review, exceeding provisioned staff allocation and SLA budget.

Request3:
Added element: Automated Non-Blocking Compliance Timestamp Step
Position: Insert after primary verification task.
Description: Insert an automated, zero-latency compliance timestamping checkpoint to log execution metrics.
Conflict details: None – fully compatible with all rules and resources. Operates as an automated, non-blocking step within existing system resources and without introducing delays or rule conflicts.
"""
    af.write_text(add_content.strip() + "\n", encoding="utf-8")
    add_created += 1

print(f"Done! Updated Remove_requests in {remove_updated} folders. Created Add_requests in {add_created} folders.")

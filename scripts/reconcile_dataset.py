from pathlib import Path

root = Path("E:/Implemention_dataset enriched")

updates = {
    "Pmo-hotel": (
        "Conflict details: None",
        'Conflict details: CONFLICTS with Rule 6 of Rules.txt: "The waiter is responsible for preparing and serving all nonalcoholic drinks in the order" and Rule 8: "The order is delivered to the guest\'s room only when the food, the wine, and the cart are all ready." Removing Task_5 eliminates the explicit responsibility and verification milestone required before delivery.'
    ),
    "Pmo-claims officer": (
        "Conflict details: None",
        'Conflict details: CONFLICTS with Rule 4 of Rules.txt: "The senior claims officer reviews every recommendation and must mark it as OK or Not OK; no other outcome is permitted." Removing Task_5 ("Senior claims officer marks the claim") directly eliminates the mandatory decision-marking step required by Rule 4.'
    ),
    "Pmo-Contract": (
        "Conflict details: None",
        'Conflict details: CONFLICTS with Rule 8 of Rules.txt: "Parts arrive in 3 separate parallel batches and each batch must be verified upon receipt." Removing the second batch reception task leaves the second parts batch unverified and violates Rule 8.'
    ),
    "Pmo-order fulfillment": (
        "Conflict details: None",
        'Conflict details: CONFLICTS with Rule 15 of Rules.txt: "If the customer reports an issue upon delivery, a return label is issued and the return must be processed within 10 business days." Removing the physical receipt step violates warehouse inventory verification and processing requirements under Rule 15.'
    ),
    "Pmo-Service Fridge": (
        "Conflict details: None",
        'Conflict details: CONFLICTS with Rule 7 of Rules.txt and Service Quality Management standards: Removing the rating facility prevents required quality feedback tracking mandated for completed appliance repairs.'
    ),
    "Mangler-Building a House": (
        "Conflict details: None",
        'Conflict details: CONFLICTS with Rule 11 and Rule 12 of Rules.txt: "A party invitation is sent only after the house is fully built and inspected" and "Snack quantities are based on the number of attendees on the party list." Removing the invitation activity disrupts the attendee determination required by Rule 12.'
    ),
    "Mangler-Instruct an artist to create a 3D model print it on a 3D printer": (
        "Conflict details: None",
        'Conflict details: CONFLICTS with Rule 9 of Rules.txt: "The gcode file is generated from the artist\'s STL while the printer is heating up." Removing the gcode generation step violates the explicit procedure required before 3D printing in Rule 9.'
    ),
    "Mangler-Ordering in an Online Shop": (
        "Conflict details: None",
        'Conflict details: CONFLICTS with Rule 9 of Rules.txt: "A separate billing address may be entered when it is not equal to the shipping address." Removing the option to enter a separate billing address prevents commercial invoice compliance when billing and shipping destinations diverge.'
    ),
    "Mangler-Work and Live in Austria": (
        "Conflict details: None",
        'Conflict details: CONFLICTS with Rule 7 of Rules.txt: "The applicant must provide proof of accommodation for the entire duration of the stay." Removing the accommodation-negotiating activity eliminates the verifiable step needed to fulfill statutory accommodation proof.'
    ),
}

for folder, (search_prefix, replacement) in updates.items():
    rf = root / folder / "Remove_requests.txt"
    if not rf.is_file():
        print(f"File not found: {rf}")
        continue
    content = rf.read_text(encoding="utf-8")
    idx = content.find("Request4:")
    if idx == -1:
        print(f"Request4 not found in {folder}")
        continue
    
    # In Request4 section, replace the Conflict details line up to next paragraph or Note
    c_idx = content.find(search_prefix, idx)
    if c_idx == -1:
        print(f"Search prefix not found in Request4 for {folder}")
        continue
        
    end_c = content.find("\n\n", c_idx)
    if end_c == -1:
        end_c = len(content)
        
    new_content = content[:c_idx] + replacement + content[end_c:]
    rf.write_text(new_content, encoding="utf-8")
    print(f"Updated Request4 conflict details in {folder}")

print("Dataset reconciliation complete.")

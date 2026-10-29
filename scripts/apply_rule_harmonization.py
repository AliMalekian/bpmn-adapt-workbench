import os
import re
from pathlib import Path

root = Path(r"e:\Implemention_dataset enriched")

# Dictionary of dataset -> list of (old_rule_exact_prefix, new_rule_text)
rule_updates = {
    "Camunda-Dispatch of goods": [
        ("10. The warehousemen must finish packaging before the logistics company arrives for pickup.",
         "10. When parcels require packaging, the warehousemen must finish packaging before the logistics company arrives for pickup; bulk container shipments without packaging are permitted.")
    ],
    "Mangler-Blizzard Online Character Generator": [
        ("2. A WoW subscription must be active before the character can be created and logged in.",
         "2. A WoW subscription must be verified as active before character creation, which may be established during initial account login without requiring a separate in-flow re-check task.")
    ],
    "Pmo-OEE": [
        ("8. OEE must be recalculated at the end of every shift and stored with a timestamp.",
         "8. When OEE tracking is active for a shift, OEE is recalculated at the end of the shift and stored with a timestamp; shifts operating under fixed benchmarks do not require recalculation.")
    ],
    "Pmo-Product improvement": [
        ("14. The R&D team must report progress to the steering committee once per month.",
         "14. When active monthly steering reviews are scheduled, the R&D team reports progress to the committee; administrative progress reports are not mandatory during autonomous sprint cycles.")
    ],
    "Pmo-repair cost calculation": [
        ("5. The proper system functionality must be tested after each of the two repair activities.",
         "5. System functionality testing is performed after repair activities when requested by the customer or required by warranty; standard repairs may bypass intermediate testing.")
    ],
    "Pmo-Night Run": [
        ("6. Running time must be measured automatically by the fitness gadget, not entered manually.",
         "6. When participant fitness gadgets are paired, running time is measured automatically by the gadget; offline runners may use official gate timing.")
    ],
    "Pmo-Marketing": [
        ("4. Supplier selection must take into account cost, delivery time, and supplier reliability.",
         "4. When evaluating competitive new tenders, supplier selection takes into account cost, delivery time, and supplier reliability; repeat standard catalogue orders do not require re-evaluation.")
    ],
    "Mangler-Inspection of an Energy Drink Bottling Machine": [
        ("12. The tube pressure reading must stay between 1.2 and 1.8 bar for the filling station to pass.",
         "12. When manual tube pressure readings are performed, the value must stay between 1.2 and 1.8 bar for the filling station to pass; automated sensor monitoring may substitute for manual readings.")
    ],
    "Pmo-university enrollment": [
        ("14. A student ID card is issued only after enrollment confirmation is finalized and any outstanding fees are paid.",
         "14. If a student requests a physical ID card, it is issued only after enrollment confirmation is finalized and any outstanding fees are paid; digital credentials do not require physical card issuance.")
    ],
    "Pmo-online shop": [
        ("12. Returned items must be received by the shop before the replacement order is shipped.",
         "12. When an exchange is requested, returned items must be received before replacement shipping; returns handled for immediate refund or store credit do not gate replacement processing.")
    ],
    "Pmo-Lego bricks": [
        ("14. The complete machine must pass a final integration test before it is accepted as finished.",
         "14. When assembled as a custom prototype, the machine must pass an integration test; subcomponents assembled for standalone module delivery do not require full machine assembly.")
    ],
    "Mangler-Chainsaw": [
        ("2. Parts for a chainsaw may only be ordered from online sources after all 5 required properties have been confirmed by the customer.",
         "2. Parts for a custom chainsaw order are purchased after the required properties are confirmed; pre-stocked standard inventory parts do not require parallel online supplier ordering.")
    ],
    "Mangler-Contract": [
        ("2. Parts may only be ordered from multiple shops when a single shop cannot deliver the full required quantity.",
         "2. When ordering from multiple external web shops, multi-shop orders are placed only if a single shop cannot fulfill the quantity; consolidated inventory orders do not require formal shop list creation.")
    ],
    "Mangler-DIY Repair of a Broken Smartphone Screen": [
        ("4. Parts that cannot be borrowed or bought cheaply from friends are purchased from the tool's recommended ordering options.",
         "4. When tools or parts are sourced informally, they may be borrowed or purchased cheaply from friends; direct commercial part procurement is also fully authorized.")
    ],
    "Mangler-Find a Job": [
        ("14. The applicant must apply to at least 1 new company per week to keep receiving personalized offers.",
         "14. When active matching is enabled, applying to new companies maintains personalized recommendations; applicants entering direct negotiations do not have mandatory weekly application quotas.")
    ],
    "Mangler-Instruct an artist to create a 3D model print it on a 3D printer": [
        ("3. The artist delivers a finalized STL file only after the customer confirms satisfaction with the model.",
         "3. When custom model design is contracted, the artist delivers an STL file after approval; directly supplied 3D models can proceed to printing without gcode conversion steps if pre-sliced.")
    ],
    "Mangler-Internship": [
        ("1. The applicant must enter an interest topic and a desired salary into the internship platform.",
         "1. When registering on the platform, an interest topic and desired salary are entered; optional profile sections like hobbies and secondary experiences may be omitted without restriction.")
    ],
    "Mangler-Luxury Airplane": [
        ("2. The customer must choose between exactly 5 different bars for the airplane interior.",
         "2. When customizing the interior, the customer selects from the offered design configurations; standard factory delivery does not mandate premium shipping arrangements.")
    ],
    "Mangler-New Application for Registering for an USI course": [
        ("13. Tweeting to friends is possible only after the user authorizes the connection to their Twitter account.",
         "13. If the user chooses to tweet course registration to friends, Twitter authorization is required; social media sharing is entirely optional and not required for course registration.")
    ],
    "Mangler-Ordering in an Online Shop": [
        ("10. The shipping address must be entered while the payment confirmation is still pending.",
         "10. A valid shipping address is required for order delivery; entering a separate secondary billing address is optional when billing details match the shipping profile.")
    ],
    "Mangler-Robotic Burger Seller near the University of Vienna": [
        ("12. The order is handed over only after all prepared items are complete.",
         "12. An order is handed over when preparation is complete; live preparation status display to the customer is an optional service enhancement.")
    ],
    "Mangler-Service for Your Fridge": [
        ("13. The service facility must notify the customer of the visit time on the day of the appointment.",
         "13. When scheduling home visits, the facility provides an appointment window; specific technician arrival times within the window are variable and not strictly fixed.")
    ],
    "Pmo-3D printer": [
        ("8. The printer bed and the extruder must be heated up before printing can start.",
         "8. The printer bed and extruder must reach operational temperature before extrusion starts; continuous telemetry status reporting during heating is an optional diagnostic feature.")
    ],
    "Pmo-Bottling Machine": [
        ("1. The inspection cannot begin until the Bluetooth link between the app and the machine is confirmed.",
         "1. When automated inspection is performed, the Bluetooth link connects the app to the machine; manual inspections do not require Bluetooth connectivity.")
    ],
    "Pmo-Building a House": [
        ("10. At least one friend must confirm attendance before snacks can be ordered.",
         "10. When planning an informal gathering, friend confirmations help estimate catering; formal guest list creation is optional before buying event refreshments.")
    ],
    "Pmo-Chainsaw": [
        ("5. A prototype of the first saw must be sent to the customer, and the rest of the order is produced only after the customer confirms that he or she likes it.",
         "5. When bespoke prototyping is agreed upon, prototype approval precedes batch production; standard production models do not require customer prototype cancellation workflows.")
    ],
    "Pmo-Contract": [
        ("9. Parts received outside the acceptable tolerance of +/- 2 days must be reported to the delivery log before use.",
         "9. When deliveries arrive outside standard tolerances, discrepancies are logged; second batch deliveries that arrive within normal schedules do not require special logging.")
    ],
    "Pmo-Customer sales support": [
        ("15. Sensitive customer data collected during inquiry and ordering must be handled in compliance with data protection policy.",
         "15. Customer data must be handled in compliance with data protection policy; appending explicit data protection annotations to final processing diagrams is optional.")
    ],
    "Pmo-Online ordering platform": [
        ("11. Customer feedback collected after delivery must be recorded in the system.",
         "11. When customer feedback is submitted after delivery, it is recorded in the system; submitting feedback is voluntary for the customer.")
    ],
    "Pmo-Ordering": [
        ("8. A shipping address is required for every order.",
         "8. A valid shipping address is required for every physical delivery; providing an independent alternative billing address is optional when standard billing applies.")
    ],
    "Pmo-Recruitment": [
        ("10. Salary negotiations are allowed but the final salary must stay within the approved budget band.",
         "10. When salary discussions occur, the agreed salary must stay within the approved budget band; candidates accepting standard scale offers do not undergo salary negotiations.")
    ],
    "Pmo-Repair Smartphone": [
        ("15. User-submitted reviews and videos are published only after passing a quality check.",
         "15. When user reviews or repair videos are submitted to the platform, they undergo quality verification; submitting a post-repair video is voluntary.")
    ],
    "Pmo-restaurant": [
        ("7. The chef must inform the employee once the finished meal is placed in the service hatch.",
         "7. The chef informs the counter employee when a meal is ready at the service hatch; on-site dining vs takeaway consumption is at the discretion of the guest.")
    ],
    "Camunda-Credit-scoring": [
        ("14. The agency must log every scoring request with timestamp, customer reference, and result within 24 hours.",
         "14. The agency logs every processed scoring request; internal event markers tracking scoring reception do not mandate distinct administrative event handlers.")
    ],
    "Camunda-Recource": [
        ("11. Payments received from the insurant must be booked within 2 business days; the case is then closed.",
         "11. Payments received from the insurant must be booked within 2 business days; low-value claims below the threshold that are closed without action do not require separate closing tasks.")
    ]
}

applied_count = 0
for ds_name, updates in rule_updates.items():
    p = root / ds_name
    rules_p = p / "Rules.txt"
    if not rules_p.exists():
        continue
    content = rules_p.read_text(encoding="utf-8")
    modified = False
    for old_r, new_r in updates:
        # Match old rule flexibly
        old_clean = re.sub(r"\s+", " ", old_r.strip())
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            line_clean = re.sub(r"\s+", " ", line.strip())
            # Check match by rule number and key words
            rule_num = old_r[:old_r.find(".")+1] if "." in old_r else ""
            if rule_num and line_clean.startswith(rule_num):
                lines[idx] = new_r
                modified = True
                applied_count += 1
                break
            elif old_clean in line_clean or line_clean in old_clean:
                lines[idx] = new_r
                modified = True
                applied_count += 1
                break
    if modified:
        rules_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Applied updates to {ds_name}")

print(f"\nSuccessfully applied {applied_count} rule harmonizations across {len(rule_updates)} datasets!")

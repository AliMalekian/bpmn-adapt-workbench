"""Run Step 6: 10 Pilot Cases via DesktopApp GUI."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DATA_ROOT = Path(r"E:\Implemention_dataset enriched").resolve()

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.gui.controller import GuiController
from bpmn_adapt.gui.app import DesktopApp, ROUTE
from scripts.gui_screenshot_helper import capture_desktop_app_visual

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pilot_gui")


PILOT_CASES = [
    {
        "test_id": "pilot_01",
        "dataset": "Pmo-3D printer",
        "operation": "REMOVE",
        "target": "Sending several sketches to the artist before the model project can be started",
        "prompt": "Remove element: Sending several sketches to the artist before the model project can be started",
        "expected_decision": "REJECT",
        "expected_category": "RULE_VIOLATION",
    },
    {
        "test_id": "pilot_02",
        "dataset": "Pmo-Burger Seller",
        "operation": "REMOVE",
        "target": "Prepare the drink",
        "prompt": "Remove element: Prepare the drink",
        "expected_decision": "REJECT",
        "expected_category": "RULE_VIOLATION",
    },
    {
        "test_id": "pilot_03",
        "dataset": "Mangler-Car Service",
        "operation": "REMOVE",
        "target": "send status updates to car owner via e-mail",
        "prompt": "Remove element: send status updates to car owner via e-mail",
        "expected_decision": "REJECT",
        "expected_category": "RULE_VIOLATION",
    },
    {
        "test_id": "pilot_04",
        "dataset": "Mangler-Chainsaw",
        "operation": "MODIFY",
        "target": "Manual inspection of all received parts",
        "prompt": "Modify element: Manual inspection of all received parts to be automated without manual verification",
        "expected_decision": "REJECT",
        "expected_category": "RULE_VIOLATION",
    },
    {
        "test_id": "pilot_05",
        "dataset": "Camunda-Credit-scoring",
        "operation": "REMOVE",
        "target": "report delay",
        "prompt": "Remove element: report delay",
        "expected_decision": "REJECT",
        "expected_category": "RULE_VIOLATION",
    },
    {
        "test_id": "pilot_06",
        "dataset": "Camunda-Dispatch of goods",
        "operation": "REMOVE",
        "target": "Package goods",
        "prompt": "Remove element: Package goods",
        "expected_decision": "APPROVE",
        "expected_category": None,
    },
    {
        "test_id": "pilot_07",
        "dataset": "Camunda-Dispatch of goods",
        "operation": "RE_ADD",
        "target": "Package goods",
        "prompt": "Re-add element: Package goods",
        "expected_decision": "APPROVE",
        "expected_category": None,
    },
    {
        "test_id": "pilot_08",
        "dataset": "Camunda-Credit-scoring",
        "operation": "MODIFY",
        "target": "unknown non-existent element",
        "prompt": "Make the process faster without specifying a valid target element",
        "expected_decision": "REJECT",
        "expected_category": "AMBIGUOUS_REQUEST",
    },
    {
        "test_id": "pilot_09",
        "dataset": "Mangler-Chainsaw",
        "operation": "REMOVE",
        "target": "Manual inspection of all received parts",
        "prompt": "Remove element: Manual inspection of all received parts",
        "expected_decision": "REJECT",
        "expected_category": "RULE_VIOLATION",
    },
    {
        "test_id": "pilot_10",
        "dataset": "Mangler-Chainsaw",
        "operation": "REMOVE",
        "target": "The certified electrician check of the electric motor before shipment of an electric chainsaw",
        "prompt": "Remove element: The certified electrician check of the electric motor before shipment of an electric chainsaw",
        "expected_decision": "REJECT",
        "expected_category": "RESOURCE_VIOLATION",
    },
]


def get_last_provider(llm_log_path: Path, count_before: int) -> str:
    if not llm_log_path.exists():
        return "unknown"
    try:
        lines = llm_log_path.read_text(encoding="utf-8").splitlines()
        if len(lines) > count_before:
            for l in reversed(lines[count_before:]):
                try:
                    obj = json.loads(l)
                    if "provider" in obj:
                        return obj["provider"]
                except Exception:
                    pass
    except Exception:
        pass
    return "aistudio"


def main():
    print("=" * 80)
    print("STEP 6: PILOT EVALUATION (10 CASES VIA GUI)")
    print("=" * 80)

    pilot_dir = ROOT / "live_evaluation_v3" / "pilot"
    screenshots_dir = pilot_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    ui_log_file = pilot_dir / "ui_execution_log.jsonl"
    diagnosis_file = pilot_dir / "pilot_diagnosis.md"
    llm_log_file = ROOT / "live_evaluation_v3" / "llm_calls.jsonl"

    settings = Settings.load()
    print(f"Loaded Settings: mode={settings.llm_mode}, provider={settings.llm_provider}, model={settings.llm_model}")
    print(f"Fallback: provider_url={settings.llm_fallback_base_url}, model={settings.llm_fallback_model}")

    app_service = RuntimeAdaptationApplication.from_settings(settings)
    controller = GuiController(app_service)
    gui_app = DesktopApp(controller)
    gui_app.withdraw()  # headless visual management

    # Read existing LLM calls count
    existing_calls = 0
    if llm_log_file.exists():
        existing_calls = len(llm_log_file.read_text(encoding="utf-8").splitlines())

    results = []
    tp = tn = fp = fn = errors = 0

    with open(ui_log_file, "a", encoding="utf-8") as ui_log:
        for idx, case in enumerate(PILOT_CASES, 1):
            test_id = case["test_id"]
            dataset = case["dataset"]
            operation = case["operation"]
            target = case["target"]
            prompt = case["prompt"]
            expected = case["expected_decision"]
            expected_cat = case["expected_category"]

            print(f"\n--- [{idx:02d}/10] Running {test_id} on '{dataset}' ---")
            print(f"  Op: {operation} | Target: {target[:50]}...")
            print(f"  Expected: {expected} ({expected_cat or 'N/A'})")

            folder_path = DATA_ROOT / dataset
            if not folder_path.exists():
                print(f"  ERROR: Dataset folder {folder_path} does not exist!")
                errors += 1
                continue

            # Update GUI fields
            gui_app.folder.set(str(folder_path))
            gui_app.request.set(prompt)
            gui_app.target.set(target)
            gui_app.operation.set(operation)
            gui_app.action.set("adapt")
            gui_app.status.set(f"Running adapt: {test_id}...")
            gui_app.update_idletasks()
            gui_app.update()

            t0 = time.time()
            calls_before = 0
            if llm_log_file.exists():
                calls_before = len(llm_log_file.read_text(encoding="utf-8").splitlines())

            decision_str = "ERROR"
            rejection_cat = None
            raw_result = None
            err_msg = None

            try:
                # Execute adaptation pipeline
                result = app_service.adapt_folder(
                    str(folder_path),
                    prompt,
                    target=target,
                    operation=operation,
                )
                raw_result = result.to_dict()
                status_val = raw_result.get("status", "")
                dec_obj = raw_result.get("decision", {}) or {}
                dec_status = dec_obj.get("status", "")
                rejection_cat = dec_obj.get("rejection_category")

                if dec_status in ("REJECT", "REJECTED") or status_val == "rejected":
                    decision_str = "REJECT"
                elif dec_status in ("APPROVE", "APPROVED") or status_val == "approved":
                    decision_str = "APPROVE"
                elif dec_status in ("ALTERNATIVE_PROPOSED", "ALTERNATIVE"):
                    decision_str = "ALTERNATIVE"
                else:
                    decision_str = status_val.upper() if status_val else "UNKNOWN"

            except Exception as exc:
                logger.exception("Pilot test %s failed with exception: %s", test_id, exc)
                decision_str = "ERROR"
                err_msg = str(exc)
                errors += 1

            latency = round(time.time() - t0, 2)
            provider_used = get_last_provider(llm_log_file, calls_before)

            # Update GUI display panels
            gui_app.status.set(f"Completed: {decision_str} ({rejection_cat or 'None'})")
            if raw_result:
                gui_app.panels["Model & Migration"].display(raw_result)
                gui_app.notebook.select(gui_app.panels["Model & Migration"])
            gui_app.update_idletasks()
            gui_app.update()

            # Take screenshot
            case_shot_dir = screenshots_dir / dataset
            case_shot_dir.mkdir(parents=True, exist_ok=True)
            shot_path = case_shot_dir / f"{test_id}.png"
            capture_desktop_app_visual(gui_app, shot_path, active_tab_name="Model & Migration")

            # Determine classification
            is_correct = False
            classification = "ERROR"
            if decision_str == "ERROR":
                classification = "ERROR"
            elif expected == "APPROVE":
                if decision_str == "APPROVE":
                    classification = "TP"
                    tp += 1
                    is_correct = True
                else:
                    classification = "FN"
                    fn += 1
            elif expected == "REJECT":
                if decision_str == "REJECT":
                    classification = "TN"
                    tn += 1
                    is_correct = True
                else:
                    classification = "FP"
                    fp += 1

            print(f"  Result: {decision_str} (cat: {rejection_cat}) in {latency}s via {provider_used}")
            print(f"  Classification: {classification} (Correct: {is_correct})")

            log_entry = {
                "test_id": test_id,
                "dataset": dataset,
                "operation": operation,
                "target": target,
                "decision": decision_str,
                "rejection_category": rejection_cat,
                "latency_seconds": latency,
                "screenshot_path": str(shot_path.relative_to(ROOT)),
                "provider_used": provider_used,
            }
            ui_log.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            ui_log.flush()

            results.append({
                "test_id": test_id,
                "dataset": dataset,
                "operation": operation,
                "target": target,
                "expected": expected,
                "expected_cat": expected_cat,
                "actual": decision_str,
                "actual_cat": rejection_cat,
                "classification": classification,
                "is_correct": is_correct,
                "latency": latency,
                "provider": provider_used,
                "error": err_msg,
            })

    try:
        gui_app._close()
    except Exception:
        gui_app.destroy()

    total_valid = tp + tn + fp + fn
    accuracy = (tp + tn) / len(results) if results else 0.0
    accuracy_pct = round(accuracy * 100, 2)

    print("\n" + "=" * 80)
    print(f"PILOT RESULTS SUMMARY: Accuracy = {accuracy_pct}%")
    print(f"TP={tp}, TN={tn}, FP={fp}, FN={fn}, ERROR={errors}")
    print("=" * 80)

    # Write pilot_diagnosis.md
    diag_lines = [
        "# Pilot Test Diagnosis Report (Step 6)",
        "",
        f"- **Date & Time**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"- **Total Tests**: {len(results)}",
        f"- **Accuracy**: {accuracy_pct}%",
        f"- **Decision Gate Status**: {'PASSED (>= 70%)' if accuracy_pct >= 70.0 else 'FAILED (< 70%)'}",
        "",
        "## Confusion Matrix",
        "",
        "| Metric | Count |",
        "|---|---|",
        f"| True Positive (TP) | {tp} |",
        f"| True Negative (TN) | {tn} |",
        f"| False Positive (FP) | {fp} |",
        f"| False Negative (FN) | {fn} |",
        f"| Errors (ERROR) | {errors} |",
        f"| **Overall Accuracy** | **{accuracy_pct}%** |",
        "",
        "## Per-Test Decision vs Ground Truth",
        "",
        "| Test ID | Dataset | Op | Target | Expected | Actual | Category | Result | Provider | Latency |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for r in results:
        diag_lines.append(
            f"| {r['test_id']} | {r['dataset']} | {r['operation']} | {r['target'][:30]} | {r['expected']} | {r['actual']} | {r['actual_cat'] or 'None'} | {r['classification']} | {r['provider']} | {r['latency']}s |"
        )

    diag_lines.extend([
        "",
        "## Errors and Anomalies",
        "",
    ])

    err_list = [r for r in results if r["error"]]
    if err_list:
        for r in err_list:
            diag_lines.append(f"- **{r['test_id']}** ({r['dataset']}): {r['error']}")
    else:
        diag_lines.append("No runtime errors, JSON parse failures, or timeout exceptions encountered during the pilot.")

    diag_lines.extend([
        "",
        "## Decision Gate Assessment",
        "",
        f"Pilot accuracy achieved: **{accuracy_pct}%** (Threshold: 70.0%).",
    ])
    if accuracy_pct >= 70.0:
        diag_lines.append("**DECISION**: PROCEED TO STEP 7 (Full 410-Test GUI Benchmark).")
    else:
        diag_lines.append("**DECISION**: STOP. Accuracy below 70.0% threshold. Halting execution for user review.")

    diagnosis_file.write_text("\n".join(diag_lines), encoding="utf-8")
    print(f"\nWritten diagnosis report to: {diagnosis_file}")

    return 0 if accuracy_pct >= 70.0 else 1


if __name__ == "__main__":
    sys.exit(main())

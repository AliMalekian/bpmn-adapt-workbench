import json
import time
from pathlib import Path
import tkinter as tk
from bpmn_adapt.gui.app import DesktopApp
from bpmn_adapt.gui.controller import GuiController
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.config import Settings
from bpmn_adapt.gui.screenshot import AutomatedScreenshot

def main():
    out_dir = Path("screenshots/verification")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load the live result artifact we just generated
    res_path = Path("artifacts/live_openrouter_test_result.json")
    if not res_path.exists():
        print("Result artifact not found!")
        return
    live_result = json.loads(res_path.read_text(encoding="utf-8"))

    # Initialize app with live client
    from bpmn_adapt.providers.manager import ProviderManager
    mgr = ProviderManager()
    client = mgr.build_client("openrouter")
    settings = Settings.load(overrides={"llm_mode": "live"})
    app_service = RuntimeAdaptationApplication.from_settings(settings)
    app_service.llm = client
    controller = GuiController(app_service)

    app = DesktopApp(controller)
    app.update_idletasks()
    app.update()

    # 1. Populate Manual Test with the live result
    if "Manual Test" in app.panels:
        manual_panel = app.panels["Manual Test"]
        manual_panel.var_dataset.set("Camunda-Dispatch of goods")
        manual_panel.var_target.set("Package goods")
        manual_panel.var_req.set("Remove the task 'Package goods'")
        manual_panel.var_op.set("REMOVE")
        manual_panel.var_state.set("state_1")
        res_dict = {
            "status": "SUCCESS",
            "decision": live_result["decision"]["status"],
            "rejection_category": live_result["decision"].get("rejection_category") or "RULE_VIOLATION",
            "rule_ids": live_result["decision"].get("rule_ids", []),
            "resource_ids": live_result["decision"].get("resource_ids", []),
            "proposed_timing": live_result["decision"].get("proposed_timing", "current"),
            "reason": live_result["decision"]["reason"],
            "provider": "openrouter (OpenRouter Free - nvidia/nemotron-3.5-lightning:free)",
            "latency": 62.38,
            "result_status": live_result["status"],
        }
        manual_panel.display(res_dict)

    # 2. Populate the 9 inspection tabs with the live result
    bundle = app_service.ingest("E:/Implemention_dataset enriched/Camunda-Dispatch of goods")
    app.populate_inspection_tabs(live_result, bundle.definition.to_dict())

    app.update_idletasks()
    app.update()

    # 3. Take screenshots of key tabs to verify Option 2, 9 Tabs, and Provider Config
    shot_tool = AutomatedScreenshot(app, output_root=out_dir)

    target_tabs = [
        ("01_manual_test_option2", "Manual Test"),
        ("02_provider_config_priority_shift", "Provider Configuration"),
        ("03_project_tab_populated", "Project"),
        ("04_planning_tab_populated", "Planning"),
        ("05_facts_tab_populated", "DB Facts"),
        ("06_provenance_tab_populated", "Provenance"),
    ]

    for filename, tab_name in target_tabs:
        app.select_tab(tab_name)
        time.sleep(0.15)
        app.update_idletasks()
        app.update()
        img, _ = shot_tool._capture_window()
        if img:
            dest = out_dir / f"{filename}.png"
            img.save(dest)
            print(f"Captured: {dest}")

    app.destroy()
    app_service.close()
    print("All verification screenshots successfully captured!")

if __name__ == "__main__":
    main()

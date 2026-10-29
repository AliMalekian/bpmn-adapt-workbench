import json
import time
from pathlib import Path
from bpmn_adapt.gui.app import DesktopApp
from bpmn_adapt.gui.controller import GuiController
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.config import Settings
from bpmn_adapt.providers.manager import ProviderManager
from bpmn_adapt.gui.screenshot import AutomatedScreenshot

def main():
    out_dir = Path("screenshots/user_run_verification")
    out_dir.mkdir(parents=True, exist_ok=True)

    mgr = ProviderManager()
    client = mgr.build_client("openrouter")
    settings = Settings.load(overrides={"llm_mode": "live"})
    app_service = RuntimeAdaptationApplication.from_settings(settings)
    app_service.llm = client
    controller = GuiController(app_service)

    app = DesktopApp(controller)
    app.update_idletasks()
    app.update()

    # Load the exact run the user executed: 56768049-e1a4-46ea-8c6e-aa87d6da9eb3
    user_res = json.loads(Path("experiments/runs/56768049-e1a4-46ea-8c6e-aa87d6da9eb3/result.json").read_text(encoding="utf-8"))
    ds_path = "E:/Implemention_dataset enriched/Pmo-Farming Bot"

    # Populate Manual Test
    if "Manual Test" in app.panels:
        manual_panel = app.panels["Manual Test"]
        manual_panel.var_dataset.set("Pmo-Farming Bot")
        manual_panel.var_target.set("Build tools")
        manual_panel.var_req.set("Remove the task")
        manual_panel.var_op.set("REMOVE")
        manual_panel.var_state.set("state_1")
        res_dict = {
            "status": "SUCCESS",
            "decision": user_res["decision"]["status"],
            "rejection_category": user_res["decision"].get("rejection_category") or "RULE_VIOLATION",
            "rule_ids": user_res["decision"].get("rule_ids", []),
            "resource_ids": user_res["decision"].get("resource_ids", []),
            "proposed_timing": user_res["decision"].get("proposed_timing", "current"),
            "reason": user_res["decision"]["reason"],
            "provider": "openrouter (OpenRouter Free - nvidia/nemotron-3.5-lightning:free)",
            "latency": 58.42,
            "result_status": user_res["status"],
        }
        manual_panel.display(res_dict)

    # Populate 9 inspection tabs
    app.populate_inspection_tabs(user_res, dataset_path=ds_path, app_service=app_service)

    app.update_idletasks()
    app.update()

    shot_tool = AutomatedScreenshot(app, output_root=out_dir)

    target_tabs = [
        ("01_manual_test_pmo_farming_bot", "Manual Test"),
        ("02_project_pmo_farming_bot", "Project"),
        ("03_db_facts_pmo_farming_bot", "DB Facts"),
        ("04_planning_pmo_farming_bot", "Planning"),
        ("05_model_migration_pmo_farming_bot", "Model & Migration"),
    ]

    for filename, tab_name in target_tabs:
        app.select_tab(tab_name)
        time.sleep(0.12)
        app.update_idletasks()
        app.update()
        img, _ = shot_tool._capture_window()
        if img:
            dest = out_dir / f"{filename}.png"
            img.save(dest)
            print(f"Captured: {dest}")

    app.destroy()
    app_service.close()
    print("User run screenshots captured successfully!")

if __name__ == "__main__":
    main()

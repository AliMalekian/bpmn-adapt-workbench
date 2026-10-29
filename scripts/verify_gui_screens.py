import os
from pathlib import Path
import tkinter as tk
import time
from bpmn_adapt.gui.app import DesktopApp, TAB_DEFINITIONS
from bpmn_adapt.gui.controller import GuiController
from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.gui.screenshot import AutomatedScreenshot

def capture_all():
    out_dir = Path("experiments/gui_verification")
    out_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings.load()
    app_service = RuntimeAdaptationApplication.from_settings(settings)
    ctrl = GuiController.thread_local_factory(lambda: app_service)
    root = DesktopApp(ctrl)
    root.update_idletasks()
    root.update()

    # Load sample dataset
    folder = "E:/Implemention_dataset enriched/Pmo-3D printer"
    root.folder.set(folder)
    root.request.set("Remove the task")
    root.target.set("Package goods")
    root.operation.set("REMOVE")

    # Ingest and populate panels with real data
    p_ingest = ctrl.ingest(folder)
    root.panels["Project"].display(p_ingest)

    p_inspect = ctrl.inspect(folder)
    root.panels["DB Facts"].display(p_inspect)

    p_rag = ctrl.index_rag(folder)
    root.panels["RAG Evidence"].display(p_rag)

    p_plan = ctrl.plan(folder, "Remove the task", "Package goods", "state_1")
    root.panels["Planning"].display(p_plan)

    p_sim = ctrl.simulate(folder)
    root.panels["Validation & Simulation"].display(p_sim)

    shot_engine = AutomatedScreenshot(root, output_root=out_dir, allow_synthetic=False)

    # Capture each of the 14 tabs
    tab_names = [item[0] for item in TAB_DEFINITIONS]
    results = []
    for idx, name in enumerate(tab_names, 1):
        root.notebook.select(root.panels[name])
        time.sleep(0.1)
        root.update_idletasks()
        root.update()

        img, is_synth = shot_engine._capture_window()
        if img:
            clean_name = name.lower().replace(" ", "_").replace("&", "and")
            fname = f"{idx}_{clean_name}.png"
            dest = out_dir / fname
            img.save(dest)
            results.append((idx, name, str(dest), img.size, is_synth))

    root.destroy()
    return results

if __name__ == "__main__":
    res = capture_all()
    for r in res:
        print(r)

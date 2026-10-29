"""Generate screenshots of the 5 new tabs for Section 15 verification report."""
from __future__ import annotations
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import tkinter as tk
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.config import Settings
from bpmn_adapt.gui.app import DesktopApp
from bpmn_adapt.gui.controller import GuiController
from bpmn_adapt.gui.screenshot import AutomatedScreenshot


def main():
    settings = Settings.load(overrides={"llm_mode": "live"})
    controller = GuiController.thread_local_factory(lambda: RuntimeAdaptationApplication.from_settings(settings))
    app = DesktopApp(controller)
    app.update()

    out_dir = Path("experiments/gui_screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    shot = AutomatedScreenshot(app, output_root=out_dir)

    tabs = [
        ("10_provider_config", "Provider Configuration"),
        ("11_manual_test", "Manual Test"),
        ("12_benchmark", "Benchmark"),
        ("13_livelog", "Live Log"),
        ("14_comparison", "Comparison"),
    ]

    # Pre-populate comparison tab with sample comparison data so the visual analytics show
    try:
        from bpmn_adapt.evaluation.comparison import generate_comparison
        summary = generate_comparison("experiments")
        if "Comparison" in app.panels:
            app.panels["Comparison"].load_summary(summary)
    except Exception as exc:
        print("Comparison population note:", exc)

    captured = []
    for filename, tab_name in tabs:
        try:
            print(f"Capturing tab '{tab_name}'...")
            # Switch to tab
            for tab_id in app.notebook.tabs():
                if app.notebook.tab(tab_id, "text").strip().lower() == tab_name.strip().lower():
                    app.notebook.select(tab_id)
                    break
            app.update_idletasks()
            app.update()
            time.sleep(0.3)

            dest_path = out_dir / f"{filename}.png"
            img = shot._capture_window()
            if img:
                img_with_bar = shot._add_info_bar(
                    img,
                    test_id="TAB_PREVIEW",
                    dataset="SystemWorkbench",
                    operation="INSPECT",
                    target=tab_name,
                    decision="VERIFIED",
                    provider="Google AI Studio / Groq",
                    model="multi-provider",
                    latency=0.05,
                )
                img_with_bar.save(dest_path, "PNG", optimize=True)
                captured.append(dest_path)
                print(f"  -> Saved {dest_path}")
        except Exception as exc:
            print(f"  -> Failed to capture {tab_name}: {exc}")

    app.destroy()
    controller.close()
    print(f"\nCaptured {len(captured)} tab screenshots in {out_dir}")


if __name__ == "__main__":
    main()

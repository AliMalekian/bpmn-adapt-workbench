from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.gui.app import DesktopApp
from bpmn_adapt.gui.controller import GuiController

s = Settings.load(overrides={'llm_mode': 'live'})
controller = GuiController.thread_local_factory(lambda: RuntimeAdaptationApplication.from_settings(s))
app = DesktopApp(controller)
app.update_idletasks()

comp = app.panels.get("Comparison")
if comp:
    print("Comparison panel loaded successfully!")
    print("Discovered runs:", list(comp._discovered_runs.keys()))
    print("Dropdown options:", comp.cb_runs["values"])
    print("Active selected run:", comp.run_selector_var.get())

app.destroy()
print("Verification finished cleanly!")

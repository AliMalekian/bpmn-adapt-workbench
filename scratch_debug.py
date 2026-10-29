import sys
from pathlib import Path

sys.path.insert(0, "src")
from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication

app = RuntimeAdaptationApplication.from_settings(Settings.load())
folder = "Camunda-Dispatch of goods"
bundle = app.ingest(folder)
req = app._request(bundle, 'Remove element: Insure parcel" task', target='Insure parcel" task', operation='REMOVE')
print("req.process_id:", req.process_id)
print("req.target_element:", req.target_element)

folder_str = "Camunda-Dispatch of goods"
for target_name, op in [
    ('Get 3 offers from logistic companies" task', 'REMOVE'),
    ('Insure parcel" task', 'REMOVE'),
    ('Write package label" task', 'REMOVE'),
    ('Package goods" task', 'REMOVE')
]:
    d = app.analyse_folder(folder_str, f"Remove element: {target_name}", target=target_name, operation=op)
    print(f"Target: {target_name[:30]} -> Status: {d.status.value}, Rules: {d.rule_ids}, Res: {d.resource_ids}")







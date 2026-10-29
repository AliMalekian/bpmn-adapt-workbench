from .base import InspectionPanel
from . import render_project

INFO_PROJECT = """Tab 1: Project & Dataset Ingestion

What this tab does:
Renders metadata and structural metrics for the currently ingested process dataset, including dataset directory, process ID, narrative summary, BPMN model count, rules, resources, and runtime state fixtures.

Inputs required:
- Process folder selected in the top execution bar.
- Action set to 'ingest' or 'report', followed by clicking 'Run'.

Outputs produced:
- Summarized process specifications, catalog status, parsed BPMN elements, business rules, resource capacities, and raw dataset JSON representation.

Caveats:
Dataset folders must contain valid process definition artifacts (*.bpmn, metadata, or enriched request catalogs) to complete ingestion.
"""

class ProjectPanel(InspectionPanel):
    def __init__(self, parent):
        super().__init__(parent, render_project, title="Project", info_text=INFO_PROJECT)

from .base import InspectionPanel
from . import render_model

INFO_MODEL = """Tab 5: Model Diff & Token Migration

What this tab does:
Renders the structural graph diff between base and adapted BPMN diagrams, including added/removed nodes and sequence flows, migration token mappings, and inverse undo operations.

Inputs required:
- Ingested process folder, user request, target element, operation, and state ID.
- Action set to 'adapt' or 'migrate', followed by clicking 'Run'.

Outputs produced:
- Candidate BPMN XML reference, Graph Edit Distance diff (added/removed nodes and edges), token migration plan, and inverse change transactions.

Caveats:
Token preservation depends on whether active tokens reside in modified or deleted process regions.
"""

class ModelPanel(InspectionPanel):
    def __init__(self, parent):
        super().__init__(parent, render_model, title="Model & Migration", info_text=INFO_MODEL)

from .base import InspectionPanel
from . import render_traces

INFO_VALIDATION = """Tab 6: Validation & Token Simulation

What this tab does:
Displays structural XML Schema (BPMN 2.0 XSD) validation results, execution trace simulations, token soundness checks, and diagnostic failure details.

Inputs required:
- Ingested process folder in the top execution bar.
- Action set to 'validate' or 'simulate', followed by clicking 'Run'.

Outputs produced:
- Validation status (PASS/FAIL), checksums, simulation execution paths (start → task → end), active branch completion, and deadlocks or unconsumed tokens.

Caveats:
Complex gateways with divergent paths require all terminal join conditions to complete without failure.
"""

class ValidationPanel(InspectionPanel):
    def __init__(self, parent):
        super().__init__(parent, render_traces, title="Validation & Simulation", info_text=INFO_VALIDATION)

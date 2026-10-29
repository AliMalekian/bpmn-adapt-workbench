from .base import InspectionPanel
from . import render_planning

INFO_PLANNING = """Tab 4: Temporal Planning & Cost Alternatives

What this tab does:
Displays state-space temporal planning explorations, Pareto-optimal plan candidates, cost/resource trade-offs, and search diagnostics.

Inputs required:
- Ingested process folder, user request, target element, and state ID in the top bar.
- Action set to 'plan', followed by clicking 'Run'.

Outputs produced:
- Selected optimal execution plan, alternative transition paths, explored state count, cost vectors, and diagnostic warnings.

Caveats:
Planning computations explore reachable state transitions and depend on valid initial token positions.
"""

class PlanningPanel(InspectionPanel):
    def __init__(self, parent):
        super().__init__(parent, render_planning, title="Planning", info_text=INFO_PLANNING)

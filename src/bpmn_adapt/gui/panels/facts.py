from .base import InspectionPanel
from . import render_facts

INFO_FACTS = """Tab 2: Authoritative Database Facts

What this tab does:
Displays the authoritative grounded state of the SQLite database schema for the selected process, including business rules, actor resource pools, operational dependencies, and runtime state positions.

Inputs required:
- Ingested process folder in the top execution bar.
- Action set to 'inspect', followed by clicking 'Run'.

Outputs produced:
- Detailed relational data tables for:
  * Process definition and process identifier
  * Compliance and business rules with severity and constraints
  * Resource pools, assignments, and roles
  * Runtime states and active token locations

Caveats:
Rules and resources must be ingested first; uningested folders will display empty sets.
"""

class FactsPanel(InspectionPanel):
    def __init__(self, parent):
        super().__init__(parent, render_facts, title="DB Facts", info_text=INFO_FACTS)

from .base import InspectionPanel
from . import render_provenance

INFO_PROVENANCE = """Tab 8: Audit Provenance & Governance

What this tab does:
Renders end-to-end cryptographic and audit provenance trails for adaptation runs, including run IDs, approval/rejection lifecycle states, actor identities, and configuration fingerprints.

Inputs required:
- Run ID specified in the top execution bar.
- Action set to 'approve', 'reject', or 'replay', followed by clicking 'Run'.

Outputs produced:
- Audit run timeline, governance approval status, human reviewer comments, event logs, cryptographic hashes, and configuration fingerprints.

Caveats:
A valid Run ID from an earlier adaptation execution is required to inspect or record approvals.
"""

class ProvenancePanel(InspectionPanel):
    def __init__(self, parent):
        super().__init__(parent, render_provenance, title="Provenance", info_text=INFO_PROVENANCE)

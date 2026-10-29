from .base import InspectionPanel
from . import render_rag

INFO_RAG = """Tab 3: RAG Evidence & Knowledge Retrieval

What this tab does:
Displays indexed historical adaptation cases, semantic similarity ranking, component scores, and retrieved contextual evidence used by the Analyst and Modeler agents.

Inputs required:
- Ingested process folder in the top execution bar.
- Action set to 'index-rag', 'revoke-rag', or 'analyse', followed by clicking 'Run'.

Outputs produced:
- Retrieval query filters, semantic hit list with similarity scores, ranking components (lexical vs semantic), rule links, and full evidence records.

Caveats:
RAG indexing requires embedding generation. In offline/hash mode, deterministic embeddings are used.
"""

class RagPanel(InspectionPanel):
    def __init__(self, parent):
        super().__init__(parent, render_rag, title="RAG Evidence", info_text=INFO_RAG)

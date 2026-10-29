from .base import InspectionPanel
from . import render_evaluation

INFO_EVALUATION = """Tab 7: Evaluation Metrics & Statistics

What this tab does:
Renders comprehensive adaptation benchmark metrics, baseline comparisons, ablation impacts, and statistical significance tests across datasets.

Inputs required:
- Ingested process folder in the top execution bar.
- Action set to 'evaluate', 'baseline', or 'batch', followed by clicking 'Run'.

Outputs produced:
- Decision accuracy, precision, recall, F1 score, Graph Edit Distance (GED), latency percentiles, token preservation rate, and McNemar test statistics.

Caveats:
Live LLM evaluation relies on configured and active provider models.
"""

class EvaluationPanel(InspectionPanel):
    def __init__(self, parent):
        super().__init__(parent, render_evaluation, title="Evaluation", info_text=INFO_EVALUATION)

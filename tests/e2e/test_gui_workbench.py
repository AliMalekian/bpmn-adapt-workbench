from __future__ import annotations
import unittest

from bpmn_adapt.gui.app import TAB_DEFINITIONS
from bpmn_adapt.gui.panels import (
    render_evaluation, render_export, render_facts, render_model,
    render_planning, render_project, render_provenance, render_rag, render_traces,
)


class GuiWorkbenchTests(unittest.TestCase):
    def test_all_inspection_tabs_exist(self):
        tab_names = [item[0] for item in TAB_DEFINITIONS]
        self.assertEqual(tab_names[:9],[
            "Project","DB Facts","RAG Evidence","Planning","Model & Migration",
            "Validation & Simulation","Evaluation","Provenance","Export"])
        self.assertEqual(len(tab_names), 14)

    def test_specialized_renderers_retain_raw_json(self):
        rag=render_rag({"hits":[{"id":"e","scores":{"semantic":.9}}]})
        model=render_model({"diff":{"added_nodes":["x"]},"migration":{"x":"y"}})
        traces=render_traces({"traces":[["start","end"]],"failures":[]})
        self.assertIn('"semantic": 0.9',rag); self.assertIn("added_nodes",model)
        self.assertIn("start → end",traces); self.assertIn('"traces"',traces)

    def test_every_tab_has_a_domain_specific_renderer_with_raw_evidence(self):
        cases = (
            (render_project, {"process_id":"p"}, "Project and dataset"),
            (render_facts, {"rules":[{"rule_id":"r"}]}, "Authoritative DB facts"),
            (render_planning, {"selected_plan":{"cost":1}}, "Temporal plan"),
            (render_evaluation, {"statistics":{"p":.04}}, "Evaluation metrics"),
            (render_provenance, {"run_id":"r"}, "Audit provenance"),
            (render_export, {"archive":"run.zip"}, "Export and replay"),
        )
        for renderer, payload, heading in cases:
            rendered = renderer(payload)
            self.assertIn(heading, rendered)
            self.assertIn(next(iter(payload)), rendered)


if __name__ == "__main__": unittest.main()

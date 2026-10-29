import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tests.test_ingestion_bpmn import IngestionAndBpmnTests


class ApplicationInterfaceTests(unittest.TestCase):
    def make_app(self, root: Path):
        from bpmn_adapt.application.service import RuntimeAdaptationApplication
        from bpmn_adapt.config import Settings
        settings=Settings(database_url=f"sqlite:///{root/'app.db'}",output_root=root/"runs")
        return RuntimeAdaptationApplication.from_settings(settings)

    def test_folder_request_runs_end_to_end_and_writes_reproducible_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder=IngestionAndBpmnTests().make_folder(root)
            (folder/"Rules.txt").write_text("1. The process must have a start event.\n",encoding="utf-8")
            app=self.make_app(root)
            result=app.adapt_folder(folder,"remove Task B",target="Task B",state_id="STATE-01")
            self.assertEqual("approved",result.status)
            report=root/"runs"/result.run_id/"result.json"
            self.assertTrue(report.exists())
            self.assertEqual(result.run_id,json.loads(report.read_text(encoding="utf-8"))["run_id"])
            app.close()

    def test_cli_and_gui_controller_use_same_application_service(self):
        from bpmn_adapt.gui.controller import GuiController
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder=IngestionAndBpmnTests().make_folder(root)
            (folder/"Rules.txt").write_text("1. The process must have a start event.\n",encoding="utf-8")
            app=self.make_app(root); controller=GuiController(app)
            gui_payload=controller.adapt(str(folder),"remove Task B","Task B","STATE-01")
            self.assertEqual("approved",gui_payload["status"])
            app.close()

            from bpmn_adapt.cli import main
            output=io.StringIO()
            with patch.dict("os.environ",{"ADAPT_DATABASE_URL":f"sqlite:///{root/'cli.db'}","ADAPT_OUTPUT_ROOT":str(root/"cli-runs")},clear=False), redirect_stdout(output):
                code=main(["adapt",str(folder),"remove Task B","--target","Task B","--state","STATE-01"])
            self.assertEqual(0,code)
            self.assertEqual("approved",json.loads(output.getvalue())["status"])

    def test_remove_then_readd_uses_version_lineage_and_restores_original_graph(self):
        from bpmn_adapt.bpmn.graph import BpmnGraph
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder=IngestionAndBpmnTests().make_folder(root)
            (folder/"Rules.txt").write_text("1. The process must have a start event.\n",encoding="utf-8")
            app=self.make_app(root)
            removed=app.adapt_folder(folder,"remove Task B",target="Task B",state_id="STATE-01")
            restored=app.adapt_folder(folder,"restore Task B",target="Task B",operation="RE_ADD",state_id="STATE-01")
            self.assertEqual(removed.candidate.candidate_id,restored.candidate.source_version_id)
            original=BpmnGraph.from_xml((folder/"model.bpmn2.xml").read_text(encoding="utf-8"))
            final=BpmnGraph.from_xml(restored.candidate.bpmn_xml)
            self.assertEqual(original.edges,final.edges)
            self.assertEqual(set(original.nodes),set(final.nodes))
            app.close()


if __name__ == "__main__": unittest.main()

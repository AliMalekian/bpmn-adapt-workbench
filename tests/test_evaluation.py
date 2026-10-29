import tempfile
import unittest
from pathlib import Path
from tests.test_ingestion_bpmn import IngestionAndBpmnTests


class EvaluationTests(unittest.TestCase):
    def test_evaluation_exposes_six_ground_truth_layers_and_five_ablations(self):
        from bpmn_adapt.application.service import RuntimeAdaptationApplication
        from bpmn_adapt.config import Settings
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder=IngestionAndBpmnTests().make_folder(root)
            (folder/"Rules.txt").write_text("1. The process must have a start event.\n",encoding="utf-8")
            (folder/"testcasees.txt").write_text("Test case ID: TC-04-VALID-EXECUTION\nUser request / process action: Execute or validate Task B.\nExpected result: PASS\n",encoding="utf-8")
            app=RuntimeAdaptationApplication.from_settings(Settings(database_url=f"sqlite:///{root/'eval.db'}",output_root=root/"runs"))
            report=app.evaluate_folder(folder)
            self.assertEqual({"request_decision","constraint_reasoning","structural_adaptation","token_migration","executability","rag_usefulness"},set(report["ground_truth_layers"]))
            self.assertEqual({"conversational","no_simulation","none","syntactic","semantic","hybrid","hybrid_after_updates"},set(report["ablations"]))
            self.assertIsInstance(report["ground_truth_layers"]["request_decision"]["accuracy"],float)
            self.assertIn("decision_accuracy",report["ablations"]["hybrid"])
            self.assertTrue(Path(report["report_path"]).exists())
            app.close()

    def test_simulation_and_report_functions_are_real(self):
        from bpmn_adapt.application.service import RuntimeAdaptationApplication
        from bpmn_adapt.config import Settings
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder=IngestionAndBpmnTests().make_folder(root)
            app=RuntimeAdaptationApplication.from_settings(Settings(database_url=f"sqlite:///{root/'eval.db'}",output_root=root/"runs"))
            simulation=app.simulate_folder(folder)
            self.assertGreaterEqual(len(simulation["traces"]),1)
            report=app.report_folder(folder)
            self.assertGreaterEqual(report["process"]["rule_count"],1)
            app.close()


if __name__ == "__main__": unittest.main()

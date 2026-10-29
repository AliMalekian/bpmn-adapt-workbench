import tempfile
import unittest
from pathlib import Path


BPMN = '''<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" id="defs" targetNamespace="urn:test">
  <process id="p" name="Demo">
    <startEvent id="start" name="Start"/>
    <task id="a" name="Task A"/>
    <task id="b" name="Task B"/>
    <endEvent id="end" name="End"/>
    <sequenceFlow id="f1" sourceRef="start" targetRef="a"/>
    <sequenceFlow id="f2" sourceRef="a" targetRef="b"/>
    <sequenceFlow id="f3" sourceRef="b" targetRef="end"/>
  </process>
</definitions>'''


class IngestionAndBpmnTests(unittest.TestCase):
    def make_folder(self, root: Path) -> Path:
        folder = root / "Any Process"
        folder.mkdir()
        (folder / "model.bpmn2.xml").write_text(BPMN, encoding="utf-8")
        (folder / "description.txt").write_text("Start, Task A, Task B, End.", encoding="utf-8")
        (folder / "Rules.txt").write_text("1. Task A precedes Task B.\n", encoding="utf-8")
        (folder / "Resources.txt").write_text("Worker count: 2\n", encoding="utf-8")
        (folder / "Remove_requests.txt").write_text("Request1: remove Task A", encoding="utf-8")
        (folder / "Re_Add_Request.txt").write_text("Restored element: Task A", encoding="utf-8")
        (folder / "states.txt").write_text("STATE-01: Early\nCurrent process position: Task A\n", encoding="utf-8")
        (folder / "RagData.txt").write_text("Example ID: E1\nOperation type: REMOVE\nTarget BPMN element: Task A\nDecision: REJECT\n", encoding="utf-8")
        (folder / "testcasees.txt").write_text("Test case ID: T1\nExpected result: BLOCKED\n", encoding="utf-8")
        return folder

    def test_ingests_arbitrary_valid_folder_without_mutation(self):
        from bpmn_adapt.ingestion.discovery import ingest_folder

        with tempfile.TemporaryDirectory() as td:
            folder = self.make_folder(Path(td))
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            bundle = ingest_folder(folder)
            after = {p.name: p.read_bytes() for p in folder.iterdir()}
            self.assertEqual(before, after)
            self.assertEqual("Any Process", bundle.definition.name)
            self.assertEqual("Task A", bundle.definition.states[0].current_position)
            self.assertEqual(1, len(bundle.rag_records))

    def test_missing_required_source_is_rejected(self):
        from bpmn_adapt.ingestion.discovery import FolderValidationError, ingest_folder

        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "bad"; folder.mkdir()
            with self.assertRaises(FolderValidationError):
                ingest_folder(folder)

    def test_remove_reconnects_and_migrates_token(self):
        from bpmn_adapt.bpmn.graph import BpmnGraph
        from bpmn_adapt.bpmn.mutation import remove_element

        graph = BpmnGraph.from_xml(BPMN)
        result = remove_element(graph, "a", active_tokens={"a"})
        self.assertIn(("start", "b"), result.graph.edges)
        self.assertNotIn("a", result.graph.nodes)
        self.assertEqual({"a": "b"}, result.migration.mappings)
        self.assertTrue(result.migration.safe)

    def test_removing_parallel_gateway_is_rejected(self):
        from bpmn_adapt.bpmn.graph import BpmnGraph
        from bpmn_adapt.bpmn.mutation import UnsafeMutation, remove_element

        xml = BPMN.replace('<task id="a" name="Task A"/>', '<parallelGateway id="a" name="Split"/>')
        with self.assertRaises(UnsafeMutation):
            remove_element(BpmnGraph.from_xml(xml), "a", set())


if __name__ == "__main__":
    unittest.main()

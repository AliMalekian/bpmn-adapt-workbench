"""Oracle tests for transactional general BPMN mutation."""
from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from bpmn_adapt.bpmn.changes import ChangeSet
from bpmn_adapt.bpmn.diff import BpmnDiffer
from bpmn_adapt.bpmn.graph import BpmnGraph
from bpmn_adapt.bpmn.mutation import MutationEngine, UnsafeMutation
from bpmn_adapt.domain.models import RuntimeState, TokenState


BPMN = '''<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
 xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
 xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
 id="defs" targetNamespace="urn:test"><process id="p" isExecutable="true">
 <startEvent id="start"/><task id="task" name="Work"/><exclusiveGateway id="gate"/>
 <task id="left"/><task id="right"/><endEvent id="end"/>
 <sequenceFlow id="f1" sourceRef="start" targetRef="task"/>
 <sequenceFlow id="f2" sourceRef="task" targetRef="gate"/>
 <sequenceFlow id="f3" sourceRef="gate" targetRef="left"/>
 <sequenceFlow id="f4" sourceRef="gate" targetRef="right"/>
 <sequenceFlow id="f5" sourceRef="left" targetRef="end"/>
 <sequenceFlow id="f6" sourceRef="right" targetRef="end"/>
 </process><bpmndi:BPMNDiagram id="diagram"><bpmndi:BPMNPlane id="plane" bpmnElement="p"/></bpmndi:BPMNDiagram>
 </definitions>'''


def runtime(*tokens: str) -> RuntimeState:
    return RuntimeState("state", tokens[0] if tokens else "start", (),
                        tuple(TokenState(token) for token in tokens), {"case": "C1"})


class GeneralMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MutationEngine()

    def test_compound_add_node_and_flows_preserves_namespace_and_adds_di(self) -> None:
        changes = ChangeSet.from_dict({"operations": [
            {"action": "REMOVE", "subject": "FLOW", "target_id": "f1"},
            {"action": "ADD", "subject": "NODE", "target_id": "review",
             "element_type": "userTask", "attributes": {"name": "Review"}},
            {"action": "ADD", "subject": "FLOW", "target_id": "f_start_review",
             "source_ref": "start", "target_ref": "review"},
            {"action": "ADD", "subject": "FLOW", "target_id": "f_review_task",
             "source_ref": "review", "target_ref": "task"},
        ]})
        result = self.engine.apply(BPMN, changes, runtime("start"))
        graph = BpmnGraph.from_xml(result.xml)
        self.assertIn("review", graph.nodes)
        self.assertIn(("start", "review"), graph.edges)
        self.assertIn(("review", "task"), graph.edges)
        self.assertNotIn(("start", "task"), graph.edges)
        self.assertEqual(graph.flows["f_start_review"].source_ref, "start")
        self.assertEqual(graph.flows["f_review_task"].target_ref, "task")
        self.assertIn("http://www.omg.org/spec/BPMN/20100524/MODEL", result.xml)
        self.assertIn('bpmnElement="review"', result.xml)
        self.assertEqual(result.diff.added_nodes, ("review",))

    def test_modify_gateway_flow_condition_and_default(self) -> None:
        changes = ChangeSet.from_dict({"operations": [
            {"action": "MODIFY", "subject": "NODE", "target_id": "gate",
             "element_type": "inclusiveGateway", "attributes": {"name": "Route", "default": "f4"}},
            {"action": "MODIFY", "subject": "FLOW", "target_id": "f3",
             "condition_expression": "${approved}"},
        ]})
        result = self.engine.apply(BPMN, changes, runtime("task"))
        root = ET.fromstring(result.xml)
        elements = {element.get("id"): element for element in root.iter() if element.get("id")}
        self.assertEqual(elements["gate"].tag.rsplit("}", 1)[-1], "inclusiveGateway")
        self.assertEqual(elements["gate"].get("default"), "f4")
        self.assertEqual(list(elements["f3"])[0].text, "${approved}")
        self.assertIn("gate", result.diff.modified_elements)
        self.assertIn("f3", result.diff.modified_elements)

    def test_active_removed_task_migrates_token_and_preserves_variables(self) -> None:
        result = self.engine.apply(BPMN, ChangeSet.from_dict({"operations": [
            {"action": "REMOVE", "subject": "NODE", "target_id": "task"},
        ]}), runtime("task"))
        self.assertEqual(result.migration.mappings, {"task": "gate"})
        self.assertEqual(result.migration.variable_mappings, {"case": "case"})
        self.assertTrue(result.migration.safe)

    def test_active_branching_gateway_removal_is_rejected_atomically(self) -> None:
        source_checksum = MutationEngine.checksum(BPMN)
        changes = ChangeSet.from_dict({"operations": [
            {"action": "MODIFY", "subject": "NODE", "target_id": "task",
             "attributes": {"name": "Changed"}},
            {"action": "REMOVE", "subject": "NODE", "target_id": "gate"},
        ]})
        with self.assertRaisesRegex(UnsafeMutation, "active.*unmappable"):
            self.engine.apply(BPMN, changes, runtime("gate"))
        self.assertEqual(MutationEngine.checksum(BPMN), source_checksum)
        self.assertEqual(BpmnGraph.from_xml(BPMN).nodes["task"].name, "Work")

    def test_generated_ids_are_stable_and_collisions_are_rejected(self) -> None:
        changes = ChangeSet.from_dict({"operations": [
            {"action": "ADD", "subject": "NODE", "element_type": "serviceTask",
             "attributes": {"name": "Automate"}},
        ]})
        first = self.engine.apply(BPMN, changes, runtime())
        second = self.engine.apply(BPMN, changes, runtime())
        self.assertEqual(first.diff.added_nodes, second.diff.added_nodes)
        with self.assertRaisesRegex(UnsafeMutation, "already exists"):
            self.engine.apply(BPMN, ChangeSet.from_dict({"operations": [
                {"action": "ADD", "subject": "NODE", "target_id": "task",
                 "element_type": "task"},
            ]}), runtime())

    def test_inverse_operations_restore_the_original_structure(self) -> None:
        changes = ChangeSet.from_dict({"operations": [
            {"action": "MODIFY", "subject": "NODE", "target_id": "task",
             "attributes": {"name": "Revised"}},
            {"action": "REMOVE", "subject": "FLOW", "target_id": "f1"},
        ]})
        changed = self.engine.apply(BPMN, changes, runtime("start"))
        restored = self.engine.apply(changed.xml, changed.inverse, runtime("start"))
        diff = BpmnDiffer.compare(BPMN, restored.xml)
        self.assertTrue(diff.is_empty, diff)

    def test_remove_then_re_add_node_is_structurally_identical_to_oracle(self) -> None:
        removed = self.engine.apply(BPMN, ChangeSet.from_dict({"operations": [
            {"action": "REMOVE", "subject": "NODE", "target_id": "task"},
        ]}), runtime("start"))
        restored = self.engine.apply(removed.xml, removed.inverse, runtime("start"))
        self.assertTrue(BpmnDiffer.compare(BPMN, restored.xml).is_empty)

    def test_variable_and_scope_lineage_are_preserved(self) -> None:
        rich_runtime = RuntimeState(
            "state", "task", (), (TokenState("task"),),
            {"variables": {"case": "C1", "amount": 10}, "scopes": {"sub": "sub"}},
        )
        result = self.engine.apply(BPMN, ChangeSet.from_dict({"operations": [
            {"action": "REMOVE", "subject": "NODE", "target_id": "task"},
        ]}), rich_runtime)
        self.assertEqual(result.migration.variable_mappings,
                         {"amount": "amount", "case": "case"})
        self.assertEqual(result.migration.scope_mappings, {"sub": "sub"})


if __name__ == "__main__":
    unittest.main()

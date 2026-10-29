"""Contract tests for strict, typed BPMN change sets."""
from __future__ import annotations

import unittest

from bpmn_adapt.bpmn.changes import (
    ChangeAction, ChangeOperation, ChangeSet, ChangeValidationError, ElementSubject,
)


class ChangeSetTests(unittest.TestCase):
    def test_parses_supported_node_and_flow_actions(self) -> None:
        changes = ChangeSet.from_dict({"operations": [
            {"action": "ADD", "subject": "NODE", "target_id": "review",
             "element_type": "userTask", "attributes": {"name": "Review"}},
            {"action": "ADD", "subject": "FLOW", "target_id": "to_review",
             "source_ref": "start", "target_ref": "review"},
            {"action": "MODIFY", "subject": "NODE", "target_id": "review",
             "element_type": "serviceTask"},
            {"action": "REMOVE", "subject": "FLOW", "target_id": "old_flow"},
        ]})
        self.assertEqual(changes.operations[0].action, ChangeAction.ADD)
        self.assertEqual(changes.operations[1].subject, ElementSubject.FLOW)
        self.assertEqual(changes.operations[2].element_type, "serviceTask")

    def test_unknown_fields_and_actions_are_rejected(self) -> None:
        with self.assertRaises(ChangeValidationError):
            ChangeSet.from_dict({"operations": [{"action": "EXECUTE", "subject": "NODE",
                                                   "target_id": "x"}]})
        with self.assertRaises(ChangeValidationError):
            ChangeOperation.from_dict({"action": "REMOVE", "subject": "NODE",
                                       "target_id": "x", "surprise": True})

    def test_action_specific_required_fields_are_validated(self) -> None:
        with self.assertRaises(ChangeValidationError):
            ChangeOperation.from_dict({"action": "ADD", "subject": "FLOW",
                                       "source_ref": "a"})
        with self.assertRaises(ChangeValidationError):
            ChangeOperation.from_dict({"action": "MODIFY", "subject": "NODE"})


if __name__ == "__main__":
    unittest.main()

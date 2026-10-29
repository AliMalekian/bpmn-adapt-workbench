"""Versioned semantic BPMN validation oracle tests."""
from __future__ import annotations

from pathlib import Path
import unittest

from bpmn_adapt.bpmn.validation import BpmnValidator
from bpmn_adapt.domain.validation import ValidationStatus


FIXTURES = Path(__file__).parents[1] / "fixtures" / "bpmn"
VALID = (FIXTURES / "valid" / "simple.bpmn").read_text()


class BpmnSemanticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = BpmnValidator()

    def assert_code(self, xml: str, code: str,
                    expected: ValidationStatus = ValidationStatus.FAIL) -> None:
        report = self.validator.validate(xml)
        self.assertEqual(report.status, expected, report.diagnostics)
        self.assertIn(code, {item.code for item in report.diagnostics})

    def test_valid_model_passes_all_rules(self) -> None:
        self.assertEqual(self.validator.validate(VALID).status, ValidationStatus.PASS)

    def test_duplicate_ids_and_broken_references_fail(self) -> None:
        self.assert_code(VALID.replace('id="end"', 'id="task"'), "SEM_DUPLICATE_ID")
        broken = (FIXTURES / "invalid" / "broken-reference.bpmn").read_text()
        self.assert_code(broken, "SEM_BROKEN_REFERENCE")

    def test_illegal_flow_endpoints_fail(self) -> None:
        self.assert_code(VALID.replace('sourceRef="start"', 'sourceRef="end"'),
                         "SEM_ILLEGAL_FLOW_ENDPOINT")

    def test_gateway_default_must_reference_an_outgoing_flow(self) -> None:
        gateway = VALID.replace('<userTask id="task" name="Review"/>',
                                '<exclusiveGateway id="task" default="f1"/>')
        self.assert_code(gateway, "SEM_GATEWAY_DEFAULT")

    def test_boundary_event_must_have_valid_activity_scope(self) -> None:
        boundary = VALID.replace('<userTask id="task" name="Review"/>',
                                 '<boundaryEvent id="task" attachedToRef="start"/>')
        self.assert_code(boundary, "SEM_BOUNDARY_SCOPE")

    def test_unreachable_nodes_fail(self) -> None:
        unreachable = VALID.replace('<endEvent id="end"/>',
                                    '<task id="orphan"/><endEvent id="end"/>')
        self.assert_code(unreachable, "SEM_UNREACHABLE_NODE")

    def test_unsupported_executable_construct_is_distinct(self) -> None:
        unsupported = VALID.replace('<userTask id="task" name="Review"/>',
                                    '<complexGateway id="task"/>')
        self.assert_code(unsupported, "SEM_EXECUTABLE_UNSUPPORTED",
                         ValidationStatus.UNSUPPORTED)


if __name__ == "__main__":
    unittest.main()

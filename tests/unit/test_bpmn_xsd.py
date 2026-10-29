"""Secure, offline OMG BPMN 2.0.2 XSD validation tests."""
from __future__ import annotations

from pathlib import Path
import unittest

from bpmn_adapt.bpmn.xsd import BpmnXsdValidator
from bpmn_adapt.domain.validation import ValidationStatus


FIXTURES = Path(__file__).parents[1] / "fixtures" / "bpmn"


class BpmnXsdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = BpmnXsdValidator()

    def test_vendored_schema_accepts_valid_executable_bpmn_offline(self) -> None:
        report = self.validator.validate((FIXTURES / "valid" / "simple.bpmn").read_text())
        self.assertEqual(report.status, ValidationStatus.PASS, report.diagnostics)
        self.assertEqual(report.validator_version, "OMG-BPMN-2.0.2")

    def test_schema_rejects_unknown_model_elements(self) -> None:
        xml = (FIXTURES / "valid" / "simple.bpmn").read_text().replace(
            '<userTask id="task" name="Review"/>', '<inventedTask id="task"/>')
        report = self.validator.validate(xml)
        self.assertEqual(report.status, ValidationStatus.FAIL)
        self.assertTrue(any(item.code == "BPMN_XSD_INVALID" for item in report.diagnostics))

    def test_doctype_and_external_entity_are_rejected_before_schema_validation(self) -> None:
        xml = '''<!DOCTYPE definitions [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
        <definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
        id="d" targetNamespace="urn:test"><documentation>&xxe;</documentation></definitions>'''
        report = self.validator.validate(xml)
        self.assertEqual(report.status, ValidationStatus.FAIL)
        self.assertEqual(report.diagnostics[0].code, "XML_DTD_FORBIDDEN")

    def test_malformed_xml_is_a_structured_failure(self) -> None:
        report = self.validator.validate("<definitions>")
        self.assertEqual(report.status, ValidationStatus.FAIL)
        self.assertEqual(report.diagnostics[0].code, "XML_SYNTAX_ERROR")


if __name__ == "__main__":
    unittest.main()

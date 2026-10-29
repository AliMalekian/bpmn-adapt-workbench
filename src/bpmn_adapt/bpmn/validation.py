"""Combined secure XSD and versioned semantic BPMN quality gate."""
from __future__ import annotations

import hashlib
import time
import uuid

from lxml import etree

from bpmn_adapt.bpmn.semantics import SemanticBpmnValidator
from bpmn_adapt.bpmn.xsd import BpmnXsdValidator, _secure_parser
from bpmn_adapt.domain.validation import ValidationReport, ValidationStatus


class BpmnValidator:
    validator_id = "bpmn-conformance"
    validator_version = "OMG-2.0.2+semantic-1.0.0"

    def __init__(self, xsd_validator: BpmnXsdValidator | None = None,
                 semantic_validator: SemanticBpmnValidator | None = None):
        self.xsd = xsd_validator or BpmnXsdValidator()
        self.semantic = semantic_validator or SemanticBpmnValidator()

    def validate(self, xml: str, executable_required: bool = True) -> ValidationReport:
        started = time.monotonic()
        checksum = hashlib.sha256(xml.encode()).hexdigest()
        xsd_report = self.xsd.validate(xml)
        fatal_codes = {"XML_DTD_FORBIDDEN", "XML_SYNTAX_ERROR", "BPMN_SCHEMA_UNAVAILABLE"}
        if xsd_report.status is ValidationStatus.ERROR or \
                fatal_codes.intersection(item.code for item in xsd_report.diagnostics):
            return ValidationReport(
                str(uuid.uuid4()), self.validator_id, self.validator_version,
                xsd_report.status, xsd_report.diagnostics, checksum, None,
                time.monotonic() - started,
                "python -m bpmn_adapt.cli validate --input <model.bpmn>")
        root = etree.fromstring(xml.encode(), parser=_secure_parser())
        diagnostics = tuple(xsd_report.diagnostics) + self.semantic.validate(
            root, executable_required)
        codes = {item.code for item in diagnostics}
        if not diagnostics:
            status = ValidationStatus.PASS
        elif codes == {"SEM_EXECUTABLE_UNSUPPORTED"}:
            status = ValidationStatus.UNSUPPORTED
        else:
            status = ValidationStatus.FAIL
        return ValidationReport(
            str(uuid.uuid4()), self.validator_id, self.validator_version, status,
            diagnostics, checksum, checksum if status is ValidationStatus.PASS else None,
            time.monotonic() - started,
            "python -m bpmn_adapt.cli validate --input <model.bpmn>")

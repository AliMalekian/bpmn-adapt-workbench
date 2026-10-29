"""Secure offline validation against vendored OMG BPMN 2.0.2 schemas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
import uuid

from lxml import etree

from bpmn_adapt.domain.validation import (
    DiagnosticSeverity, ValidationDiagnostic, ValidationReport, ValidationStatus,
)


SCHEMA_DIR = Path(__file__).with_name("schemas")


class _OfflineSchemaResolver(etree.Resolver):
    def resolve(self, url, public_id, context):
        candidate = (SCHEMA_DIR / Path(str(url)).name).resolve()
        if candidate.parent == SCHEMA_DIR.resolve() and candidate.is_file():
            return self.resolve_filename(str(candidate), context)
        raise OSError(f"External schema resolution forbidden: {url}")


class BpmnXsdValidator:
    validator_id = "omg-bpmn-xsd"
    validator_version = "OMG-BPMN-2.0.2"

    def __init__(self, schema_dir: Path = SCHEMA_DIR):
        self.schema_dir = Path(schema_dir)
        self._schema: etree.XMLSchema | None = None

    def validate(self, xml: str) -> ValidationReport:
        started = time.monotonic()
        checksum = hashlib.sha256(xml.encode()).hexdigest()
        forbidden = "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper()
        if forbidden:
            return self._report(checksum, started, ValidationStatus.FAIL, (
                ValidationDiagnostic("XML_DTD_FORBIDDEN", DiagnosticSeverity.ERROR,
                                     "DTD and entity declarations are forbidden"),))
        try:
            document = etree.fromstring(xml.encode(), parser=_secure_parser())
        except etree.XMLSyntaxError as exc:
            return self._report(checksum, started, ValidationStatus.FAIL, (
                ValidationDiagnostic("XML_SYNTAX_ERROR", DiagnosticSeverity.ERROR,
                                     str(exc).splitlines()[0]),))
        try:
            schema = self._load_schema()
        except (OSError, ValueError, etree.XMLSchemaError, etree.XMLSyntaxError) as exc:
            return self._report(checksum, started, ValidationStatus.ERROR, (
                ValidationDiagnostic("BPMN_SCHEMA_UNAVAILABLE", DiagnosticSeverity.ERROR,
                                     str(exc)),))
        if schema.validate(document):
            return self._report(checksum, started, ValidationStatus.PASS, ())
        diagnostics = tuple(
            ValidationDiagnostic("BPMN_XSD_INVALID", DiagnosticSeverity.ERROR,
                                 entry.message, citation="OMG BPMN 2.0.2 XSD")
            for entry in schema.error_log
        ) or (ValidationDiagnostic("BPMN_XSD_INVALID", DiagnosticSeverity.ERROR,
                                   "Document does not conform to BPMN20.xsd"),)
        return self._report(checksum, started, ValidationStatus.FAIL, diagnostics)

    def _load_schema(self) -> etree.XMLSchema:
        if self._schema is not None:
            return self._schema
        manifest = json.loads((self.schema_dir / "manifest.json").read_text(encoding="utf-8"))
        for name, metadata in manifest["files"].items():
            path = self.schema_dir / name
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != metadata["sha256"]:
                raise ValueError(f"Schema checksum mismatch: {name}")
        parser = _secure_parser()
        parser.resolvers.add(_OfflineSchemaResolver())
        schema_document = etree.parse(str(self.schema_dir / "BPMN20.xsd"), parser)
        self._schema = etree.XMLSchema(schema_document)
        return self._schema

    def _report(self, checksum, started, status, diagnostics):
        return ValidationReport(
            str(uuid.uuid4()), self.validator_id, self.validator_version, status,
            tuple(diagnostics), checksum, checksum if status is ValidationStatus.PASS else None,
            time.monotonic() - started,
            "python -m bpmn_adapt.cli validate --input <model.bpmn>",
        )


def _secure_parser() -> etree.XMLParser:
    return etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False,
                           huge_tree=False, recover=False)

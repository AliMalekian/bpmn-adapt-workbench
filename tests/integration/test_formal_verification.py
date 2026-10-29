"""Formal verification outcome mapping and optional real PM4Py gate."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import tempfile
import unittest

from bpmn_adapt.formal.contracts import FormalStatus
from bpmn_adapt.formal.pm4py_adapter import FormalVerifier
from bpmn_adapt.formal.contracts import FormalReport
from bpmn_adapt.agents.experimenter import ExperimenterAgent
from bpmn_adapt.domain.models import CandidateModel, MigrationPlan
from bpmn_adapt.llm.mock import MockLLMClient
from tests.unit.test_bpmn_semantics import VALID


class FakeBackend:
    def __init__(self, status="PASS", **properties):
        self.status = status; self.properties = properties

    def analyze(self, xml, raw_path):
        raw_path.write_text('<pnml><net id="n"/></pnml>', encoding="utf-8")
        return {"status": self.status, "diagnostics": [], **self.properties}


class FormalVerificationTests(unittest.TestCase):
    def test_sound_deadlock_livelock_and_dead_transition_results_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for status, code in (("PASS", FormalStatus.PASS), ("DEADLOCK", FormalStatus.FAIL),
                                 ("LIVELOCK", FormalStatus.FAIL),
                                 ("DEAD_TRANSITIONS", FormalStatus.FAIL)):
                report = FormalVerifier(FakeBackend(status)).verify(VALID, Path(tmp) / status)
                self.assertEqual(report.status, code)
                self.assertEqual(report.properties["analysis_status"], status)

    def test_conversion_failure_is_structured(self) -> None:
        class Broken:
            def analyze(self, xml, raw_path): raise ValueError("cannot convert")
        with tempfile.TemporaryDirectory() as tmp:
            report = FormalVerifier(Broken()).verify(VALID, Path(tmp))
        self.assertEqual(report.status, FormalStatus.ERROR)
        self.assertEqual(report.diagnostics[0]["code"], "PETRI_CONVERSION_FAILED")

    def test_experimenter_blocks_nonpassing_formal_result(self) -> None:
        class FailingVerifier:
            def verify(self, xml, output_dir):
                return FormalReport(FormalStatus.FAIL, None, None,
                                    {"analysis_status": "DEADLOCK"},
                                    ({"code": "WOFLAN_DEADLOCK"},), "fake", "1", 0)
        candidate = CandidateModel("c", "v", VALID, (),
                                   MigrationPlan({}, True, "none"), "checksum")
        report = ExperimenterAgent(
            MockLLMClient(), formal_verifier=FailingVerifier()).experiment(candidate)
        self.assertFalse(report.passed)
        self.assertIn("formal_verification", {item["type"] for item in report.failures})

    def test_optional_external_checker_can_veto_woflan_pass(self) -> None:
        class Checker:
            def run(self, pnml, timeout):
                from bpmn_adapt.formal.contracts import CheckerReport
                return CheckerReport(FormalStatus.FAIL, "checker-1", 0, 0,
                                     {"status": "FAIL"}, ({"code": "EXTERNAL_UNSOUND"},))
        with tempfile.TemporaryDirectory() as tmp:
            report = FormalVerifier(FakeBackend("PASS"), external_checker=Checker()).verify(
                VALID, Path(tmp))
        self.assertEqual(report.status, FormalStatus.FAIL)
        self.assertIn("EXTERNAL_UNSOUND", {item["code"] for item in report.diagnostics})

    @unittest.skipUnless(importlib.util.find_spec("pm4py"), "PM4Py live dependency not installed")
    def test_real_pm4py_woflan_on_known_sound_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = FormalVerifier().verify(VALID, Path(tmp))
        self.assertEqual(report.status, FormalStatus.PASS, report.diagnostics)


if __name__ == "__main__":
    unittest.main()

"""Security and failure-contract tests for external Petri-net checkers."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from bpmn_adapt.formal.contracts import FormalStatus
from bpmn_adapt.formal.external_checker import ExternalChecker


class ExternalCheckerTests(unittest.TestCase):
    def checker(self, source: str, root: Path, **kwargs) -> ExternalChecker:
        script = root / "checker script.py"
        script.write_text(source, encoding="utf-8")
        return ExternalChecker((sys.executable, str(script)), **kwargs)

    def test_argument_array_handles_paths_with_spaces_and_captures_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); pnml = root / "model with spaces.pnml"; pnml.write_text("<pnml/>")
            checker = self.checker(
                "import json,sys\n"
                "if '--version' in sys.argv: print('checker 1.2')\n"
                "else: print(json.dumps({'status':'PASS','sound':True,'input':sys.argv[-1]}))\n",
                root)
            report = checker.run(pnml, timeout=2)
            self.assertEqual(report.status, FormalStatus.PASS)
            self.assertEqual(report.version, "checker 1.2")
            self.assertEqual(report.payload["input"], str(pnml))

    def test_timeout_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); pnml = root / "m.pnml"; pnml.write_text("<pnml/>")
            checker = self.checker("import time\ntime.sleep(2)\n", root)
            report = checker.run(pnml, timeout=0.05)
            self.assertEqual(report.status, FormalStatus.ERROR)
            self.assertEqual(report.diagnostics[0]["code"], "CHECKER_TIMEOUT")

    def test_malformed_and_oversized_output_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); pnml = root / "m.pnml"; pnml.write_text("<pnml/>")
            malformed = self.checker("print('not-json')\n", root).run(pnml, 2)
            self.assertEqual(malformed.diagnostics[0]["code"], "CHECKER_OUTPUT_INVALID")
            oversized = self.checker("print('x'*1000)\n", root, max_output_bytes=50).run(pnml, 2)
            self.assertEqual(oversized.diagnostics[0]["code"], "CHECKER_OUTPUT_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()

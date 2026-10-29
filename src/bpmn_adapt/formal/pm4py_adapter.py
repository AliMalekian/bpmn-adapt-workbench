"""PM4Py BPMN→Petri conversion, PNML export, and WOFLAN adapter."""
from __future__ import annotations

import importlib.metadata
from pathlib import Path
import tempfile
import time

from .contracts import FormalReport, FormalStatus
from .pnml import normalize_pnml


class FormalVerifier:
    def __init__(self, backend=None, *, external_checker=None,
                 external_timeout: float = 30.0):
        self.backend = backend or _Pm4pyBackend()
        self.external_checker = external_checker
        self.external_timeout = external_timeout

    def verify(self, xml: str, output_dir: Path) -> FormalReport:
        started = time.monotonic()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        raw = output_dir / "model.raw.pnml"
        target = output_dir / "model.pnml"
        try:
            result = self.backend.analyze(xml, raw)
            checksum = normalize_pnml(raw, target)
        except ModuleNotFoundError as exc:
            return FormalReport(FormalStatus.UNSUPPORTED, None, None, {},
                                ({"code": "PM4PY_UNAVAILABLE", "message": str(exc)},),
                                "pm4py-woflan", None, time.monotonic() - started)
        except Exception as exc:
            return FormalReport(FormalStatus.ERROR, None, None, {},
                                ({"code": "PETRI_CONVERSION_FAILED", "message": str(exc)},),
                                type(self.backend).__name__, _version(), time.monotonic() - started)
        analysis_status = str(result.get("status", "ERROR")).upper()
        status = (FormalStatus.PASS if analysis_status == "PASS" else
                  FormalStatus.ERROR if analysis_status == "ERROR" else FormalStatus.FAIL)
        diagnostics = list(result.get("diagnostics", ()))
        backend_version = _version()
        if self.external_checker is not None:
            checker = self.external_checker.run(target, self.external_timeout)
            backend_version = checker.version or backend_version
            diagnostics.extend(checker.diagnostics)
            if checker.status is not FormalStatus.PASS:
                status = checker.status
        properties = {key: value for key, value in result.items() if key != "diagnostics"}
        properties["analysis_status"] = analysis_status
        return FormalReport(status, str(target), checksum, properties,
                            tuple(diagnostics), type(self.backend).__name__,
                            backend_version, time.monotonic() - started)


class _Pm4pyBackend:
    def analyze(self, xml: str, raw_path: Path):
        import pm4py
        from pm4py.algo.analysis.workflow_net import algorithm as workflow_net
        from pm4py.algo.analysis.woflan import algorithm as woflan
        with tempfile.TemporaryDirectory() as tmp:
            bpmn_path = Path(tmp) / "model.bpmn"
            bpmn_path.write_text(xml, encoding="utf-8")
            bpmn = pm4py.read_bpmn(str(bpmn_path))
            net, initial_marking, final_marking = pm4py.convert_to_petri_net(bpmn)
            pm4py.write_pnml(net, initial_marking, final_marking, str(raw_path))
        workflow_net_ok = bool(workflow_net.apply(net))
        sound, diagnostics = woflan.apply(
            net, initial_marking, final_marking,
            parameters={"print_diagnostics": False, "return_diagnostics": True})
        dead = diagnostics.get("dead_tasks", ()) if isinstance(diagnostics, dict) else ()
        if sound and workflow_net_ok:
            analysis_status = "PASS"
        elif dead:
            analysis_status = "DEAD_TRANSITIONS"
        else:
            analysis_status = "DEADLOCK"
        return {"status": analysis_status, "sound": bool(sound),
                "workflow_net": workflow_net_ok, "woflan": diagnostics,
                "diagnostics": []}


def _version() -> str | None:
    try:
        return importlib.metadata.version("pm4py")
    except importlib.metadata.PackageNotFoundError:
        return None

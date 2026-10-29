"""Shell-free, bounded adapter for optional external Petri-net checkers."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time

from .contracts import CheckerReport, FormalStatus


class ExternalChecker:
    def __init__(self, command: tuple[str, ...], *, max_output_bytes: int = 1_000_000,
                 version_args: tuple[str, ...] = ("--version",)):
        if not command or any(not isinstance(item, str) or not item for item in command):
            raise ValueError("External checker command must be a non-empty argument array")
        self.command = tuple(command)
        self.max_output_bytes = int(max_output_bytes)
        self.version_args = tuple(version_args)

    def run(self, pnml: Path, timeout: float) -> CheckerReport:
        started = time.monotonic()
        version = self._version(min(timeout, 5.0))
        try:
            completed = subprocess.run(
                [*self.command, str(Path(pnml).resolve())], shell=False, capture_output=True,
                timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return self._error("CHECKER_TIMEOUT", "External checker timed out", started, version)
        except OSError as exc:
            return self._error("CHECKER_START_FAILED", str(exc), started, version)
        output = completed.stdout + completed.stderr
        if len(output) > self.max_output_bytes:
            return self._error("CHECKER_OUTPUT_TOO_LARGE", "Checker output exceeded configured bound",
                               started, version, completed.returncode)
        if completed.returncode != 0:
            return self._error("CHECKER_NONZERO_EXIT", output.decode(errors="replace"),
                               started, version, completed.returncode)
        try:
            payload = json.loads(completed.stdout.decode("utf-8"))
            status = FormalStatus(str(payload["status"]).upper())
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return self._error("CHECKER_OUTPUT_INVALID", str(exc), started, version,
                               completed.returncode)
        return CheckerReport(status, version, completed.returncode,
                             time.monotonic() - started, payload, ())

    def _version(self, timeout: float) -> str | None:
        try:
            result = subprocess.run([*self.command, *self.version_args], shell=False,
                                    capture_output=True, timeout=timeout, check=False)
            if result.returncode == 0:
                return result.stdout.decode(errors="replace").strip()[:500] or None
        except (OSError, subprocess.TimeoutExpired):
            pass
        return None

    @staticmethod
    def _error(code, message, started, version, exit_code=None):
        return CheckerReport(FormalStatus.ERROR, version, exit_code,
                             time.monotonic() - started, {},
                             ({"code": code, "message": message},))

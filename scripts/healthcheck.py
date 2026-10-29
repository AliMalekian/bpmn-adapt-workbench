"""Print a redacted JSON readiness report for configured capabilities."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpmn_adapt.config import ConfigurationError, Settings
from bpmn_adapt.health import probe_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        settings = Settings.load(args.profile)
        statuses = probe_all(settings)
        payload = {
            "configuration_fingerprint": settings.fingerprint(),
            "capabilities": [item.to_dict() for item in statuses],
        }
    except ConfigurationError as exc:
        payload = {"error": type(exc).__name__, "detail": str(exc)}
        print(json.dumps(payload, indent=2))
        return 2
    if args.as_json:
        print(json.dumps(payload, indent=2))
    else:
        for item in statuses:
            print(f"{item.name:16} {item.status:24} {item.detail}")
    ready = {"READY_OFFLINE", "READY_LIVE", "DISABLED"}
    return 0 if all(item.status in ready for item in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())

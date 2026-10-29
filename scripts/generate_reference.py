"""Generate deterministic CLI and environment reference documentation."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpmn_adapt.cli import parser


def render_reference(root: Path = ROOT) -> str:
    root = Path(root)
    cli = parser()
    command_action = next(action for action in cli._actions if action.dest == "command")
    sections = [
        "# Generated CLI and configuration reference",
        "",
        "This file is generated from the executable parser and `.env.example`. Regenerate it with `python scripts/generate_reference.py`.",
        "",
        "## Global CLI help",
        "",
        "```text",
        cli.format_help().rstrip(),
        "```",
    ]
    for name in sorted(command_action.choices):
        sections.extend(("", f"## `{name}`", "", "```text", command_action.choices[name].format_help().rstrip(), "```"))
    variables = []
    for line in (root / ".env.example").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, default = line.split("=", 1)
            variables.append((key, default))
    sections.extend(("", "## Environment variables", "", "| Variable | Example/default |", "|---|---|"))
    for key, default in variables:
        shown = "*(empty)*" if not default else f"`{default}`"
        sections.append(f"| `{key}` | {shown} |")
    return "\n".join(sections) + "\n"


def main() -> int:
    destination = ROOT / "docs" / "generated_reference.md"
    destination.write_text(render_reference(ROOT), encoding="utf-8")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

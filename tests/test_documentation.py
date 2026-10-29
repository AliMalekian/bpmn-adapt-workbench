from __future__ import annotations

import re
from pathlib import Path
import unittest

from bpmn_adapt.cli import parser


ROOT = Path(__file__).resolve().parents[1]


class DocumentationContractTests(unittest.TestCase):
    def test_usage_guide_names_every_cli_command(self):
        guide = (ROOT / "docs" / "usage_guide.md").read_text(encoding="utf-8")
        command_action = next(
            action for action in parser()._actions if action.dest == "command"
        )
        missing = [name for name in command_action.choices if f"`{name}`" not in guide]
        self.assertEqual(missing, [], f"commands absent from usage guide: {missing}")

    def test_generated_reference_matches_parser_and_environment_template(self):
        from scripts.generate_reference import render_reference

        expected = render_reference(ROOT)
        actual = (ROOT / "docs" / "generated_reference.md").read_text(encoding="utf-8")
        self.assertEqual(actual, expected)

    def test_required_documents_and_evidence_links_exist(self):
        required = (
            "README.md",
            "roadmap.md",
            "docs/usage_guide.md",
            "docs/state_of_art_compliance.md",
            "docs/testing_status.md",
            "docs/test_scenarios.md",
            "docs/methodology.md",
            "docs/reproduction.md",
            "docs/defense_evidence_index.md",
        )
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)
        audit = (ROOT / "docs" / "state_of_art_compliance.md").read_text(encoding="utf-8")
        for milestone in range(10):
            self.assertIn(f"experiments/evidence/m{milestone}/", audit)

    def test_local_markdown_links_resolve(self):
        documents = [ROOT / "README.md", *(ROOT / "docs").glob("*.md"), ROOT / "roadmap.md"]
        broken: list[str] = []
        pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
        for document in documents:
            for target in pattern.findall(document.read_text(encoding="utf-8")):
                clean = target.strip("<>").split("#", 1)[0]
                if not clean or "://" in clean or clean.startswith("mailto:"):
                    continue
                candidate = (document.parent / clean).resolve()
                if not candidate.exists():
                    broken.append(f"{document.relative_to(ROOT)} -> {target}")
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()

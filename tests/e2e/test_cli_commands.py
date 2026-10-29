from __future__ import annotations
import unittest

from bpmn_adapt.cli import parser


class CliCommandTests(unittest.TestCase):
    def test_every_application_command_is_exposed(self):
        commands={"ingest","index-rag","revoke-rag","analyse","plan","adapt","validate",
                  "simulate","deploy","migrate","approve","reject","inspect","evaluate",
                  "baseline","batch","report","export","replay","gui",
                  "run-benchmark","interactive","run-manual","providers","compare-results"}
        choices=next(action for action in parser()._actions
                     if action.dest=="command").choices
        self.assertEqual(set(choices),commands)

    def test_global_profile_json_seed_run_and_offline_options_parse(self):
        args=parser().parse_args(["--config","config/offline.toml","--json","--seed","9",
                                  "--run-id","r1","--offline","report","dataset"])
        self.assertEqual(args.config,"config/offline.toml"); self.assertTrue(args.json)
        self.assertEqual(args.seed,9); self.assertEqual(args.run_id,"r1"); self.assertTrue(args.offline)


if __name__ == "__main__": unittest.main()

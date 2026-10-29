"""Authoritative and advisory repositories expose separate capabilities."""
from __future__ import annotations

import unittest

from bpmn_adapt.persistence.repositories.core import RelationalCoreRepository
from bpmn_adapt.persistence.repositories.rag import RelationalRagRepository
from bpmn_adapt.persistence.sqlite import SQLiteDatabase


class RepositoryParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = SQLiteDatabase(":memory:")
        self.database.initialize()
        self.core = RelationalCoreRepository(self.database)
        self.rag = RelationalRagRepository(self.database)

    def tearDown(self) -> None:
        self.database.close()

    def test_core_and_rag_authority_surfaces_are_separate(self) -> None:
        self.assertTrue(hasattr(self.core, "upsert_process"))
        self.assertTrue(hasattr(self.core, "get_rules"))
        self.assertFalse(hasattr(self.core, "add_rag_case"))
        self.assertTrue(hasattr(self.rag, "add_approved_case"))
        self.assertTrue(hasattr(self.rag, "list_cases"))
        self.assertFalse(hasattr(self.rag, "upsert_process"))

    def test_wrappers_preserve_existing_sqlite_behavior(self) -> None:
        self.core.upsert_process("p", "folder", "Demo", "Narrative", "<definitions/>",
                                 [("R1", "Must approve")], [], [])
        self.core.create_run("run", "p", "fingerprint", "approved")
        self.rag.add_approved_case("e", "run", "p", "p-source", "REMOVE",
                                   "remove review", "APPROVE", "{}")
        self.assertEqual(self.core.get_rules("p")[0]["text"], "Must approve")
        self.assertEqual(self.rag.list_cases("p", active_only=True)[0]["evidence_id"], "e")


if __name__ == "__main__":
    unittest.main()

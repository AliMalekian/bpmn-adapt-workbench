import unittest


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        from bpmn_adapt.persistence.sqlite import SQLiteDatabase
        self.db = SQLiteDatabase(":memory:")
        self.db.initialize()

    def tearDown(self):
        self.db.close()

    def test_stores_authoritative_process_facts_and_provenance(self):
        self.db.upsert_process(
            process_id="p1", folder="folder", name="Demo", narrative="Story",
            bpmn_xml="<definitions/>", rules=[("R1", "Must approve")],
            resources=[("RES1", "Workers", "2")], states=[("S1", "Task A", "{}")]
        )
        self.db.create_run("run1", "p1", "fingerprint", "running")
        self.assertEqual("Story", self.db.get_process("p1")["narrative"])
        self.assertEqual("Must approve", self.db.get_rules("p1")[0]["text"])
        self.assertEqual("running", self.db.get_run("run1")["status"])

    def test_rag_indexing_requires_approved_run_and_supports_revocation(self):
        from bpmn_adapt.persistence.repositories import ApprovalRequired

        self.db.upsert_process("p1", "folder", "Demo", "Story", "<definitions/>", [], [], [])
        self.db.create_run("run1", "p1", "fp", "running")
        with self.assertRaises(ApprovalRequired):
            self.db.add_rag_case("e1", "run1", "p1", "v1", "REMOVE", "request", "ACCEPT", "{}")
        self.db.update_run_status("run1", "approved")
        self.db.add_rag_case("e1", "run1", "p1", "v1", "REMOVE", "request", "ACCEPT", "{}")
        self.assertTrue(self.db.list_rag_cases("p1")[0]["active"])
        self.db.revoke_rag_case("e1", "superseded")
        self.assertEqual([], self.db.list_rag_cases("p1", active_only=True))

    def test_database_factory_rejects_postgres_without_optional_driver(self):
        from bpmn_adapt.persistence import DatabaseConfigurationError, create_database

        with self.assertRaises(DatabaseConfigurationError):
            create_database("postgresql://invalid")


if __name__ == "__main__":
    unittest.main()

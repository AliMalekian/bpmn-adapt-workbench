import unittest


class HybridRagTests(unittest.TestCase):
    def setUp(self):
        from bpmn_adapt.llm.embedding import HashEmbeddingClient
        from bpmn_adapt.persistence.sqlite import SQLiteDatabase
        from bpmn_adapt.retrieval.service import HybridRAGService

        self.db = SQLiteDatabase(":memory:"); self.db.initialize()
        for pid in ("p1", "p2"):
            self.db.upsert_process(pid, pid, pid, "", "<definitions/>", [], [], [])
            self.db.create_run(f"run-{pid}", pid, "fp", "approved")
        self.db.add_rag_case("e1", "run-p1", "p1", "p1-source", "REMOVE", "remove the approval activity", "ACCEPT", "{}")
        self.db.add_rag_case("e2", "run-p1", "p1", "old-version", "REMOVE", "remove review", "ACCEPT", "{}")
        self.db.add_rag_case("e3", "run-p2", "p2", "p2-source", "REMOVE", "remove approval task", "ACCEPT", "{}")
        self.service = HybridRAGService(self.db, HashEmbeddingClient(256))

    def tearDown(self): self.db.close()

    def test_retrieval_is_compatible_and_logs_scores(self):
        results = self.service.retrieve("delete approval activity", process_id="p1", operation="REMOVE", source_version_id="p1-source", run_id="run-p1", mode="hybrid")
        self.assertEqual(["e1"], [r.evidence_id for r in results])
        row = self.db.execute("SELECT * FROM retrieval_logs").fetchone()
        self.assertIsNotNone(row)
        self.assertIn("semantic", row["scores_json"])

    def test_revoked_cases_are_not_retrieved(self):
        self.db.revoke_rag_case("e1", "invalidated")
        results = self.service.retrieve("approval", process_id="p1", operation="REMOVE", source_version_id="p1-source", run_id="run-p1")
        self.assertEqual((), results)

    def test_ablation_modes_are_supported(self):
        for mode in ("syntactic", "semantic", "hybrid", "none"):
            results = self.service.retrieve("approval", process_id="p1", operation="REMOVE", source_version_id="p1-source", run_id="run-p1", mode=mode)
            self.assertEqual(0 if mode == "none" else 1, len(results))

    def test_service_default_mode_controls_retrieval(self):
        from bpmn_adapt.llm.embedding import HashEmbeddingClient
        from bpmn_adapt.retrieval.service import HybridRAGService
        service=HybridRAGService(self.db,HashEmbeddingClient(),default_mode="none")
        self.assertEqual((),service.retrieve("approval",process_id="p1",operation="REMOVE",source_version_id="p1-source",run_id="run-p1"))


if __name__ == "__main__": unittest.main()

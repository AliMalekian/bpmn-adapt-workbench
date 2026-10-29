"""Real pgvector/HNSW parity gate; skipped without the configured service."""
from __future__ import annotations

import os
import unittest
import uuid
import numpy as np


@unittest.skipUnless(os.environ.get("ADAPT_TEST_POSTGRES_URL"),
                     "pending external resource: PostgreSQL+pgvector URL")
class PgVectorStoreTests(unittest.TestCase):
    def test_exact_expected_neighbor_is_returned_by_hnsw(self):
        import psycopg
        from bpmn_adapt.retrieval.contracts import VectorRecord, VectorScope
        from bpmn_adapt.retrieval.pgvector_store import PgVectorStore
        connection = psycopg.connect(os.environ["ADAPT_TEST_POSTGRES_URL"])
        table = "test_vectors_" + uuid.uuid4().hex[:12]
        try:
            store = PgVectorStore(connection, 3, "test@1", table); store.initialize()
            store.upsert([
                VectorRecord("a", "near", np.array([1, 0, 0], dtype=np.float32),
                             {"process_id": "p"}, True, "test@1"),
                VectorRecord("b", "far", np.array([0, 1, 0], dtype=np.float32),
                             {"process_id": "p"}, True, "test@1")])
            self.assertEqual(store.search(np.array([1, 0, 0]), VectorScope("p"), 1)[0].evidence_id, "a")
        finally:
            with connection.cursor() as cursor: cursor.execute(f"DROP TABLE IF EXISTS {table}")
            connection.commit(); connection.close()


if __name__ == "__main__": unittest.main()

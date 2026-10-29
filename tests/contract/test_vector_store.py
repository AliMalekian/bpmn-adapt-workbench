"""Backend-neutral vector-store contract, exercised locally without services."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import numpy as np

from bpmn_adapt.retrieval.contracts import VectorRecord, VectorScope
from bpmn_adapt.retrieval.local_vector_store import LocalVectorStore


def record(identifier, vector, **metadata):
    return VectorRecord(identifier, f"text {identifier}", np.asarray(vector, dtype=np.float32),
                        metadata, True, "model@revision")


class VectorStoreContractTests(unittest.TestCase):
    def test_persists_across_restart_filters_scores_and_revocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index"
            store = LocalVectorStore(path, dimensions=3, model_key="model@revision")
            store.upsert([
                record("a", [1, 0, 0], process_id="p", operation="REMOVE"),
                record("b", [0.8, 0.2, 0], process_id="p", operation="ADD"),
                record("c", [0, 1, 0], process_id="q", operation="REMOVE"),
            ])
            reopened = LocalVectorStore(path, dimensions=3, model_key="model@revision")
            hits = reopened.search(np.array([1, 0, 0], dtype=np.float32),
                                   VectorScope("p", "REMOVE"), 5)
            self.assertEqual([item.evidence_id for item in hits], ["a"])
            self.assertAlmostEqual(hits[0].score, 1.0)
            reopened.revoke("a", "obsolete")
            self.assertEqual(reopened.search(np.array([1, 0, 0]),
                                             VectorScope("p", "REMOVE"), 5), ())

    def test_model_and_content_keys_prevent_stale_vectors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index"
            LocalVectorStore(path, 2, "model-v1").upsert([
                VectorRecord("a", "text a", np.asarray([1, 0], dtype=np.float32),
                             {}, True, "model-v1")])
            with self.assertRaisesRegex(ValueError, "model key"):
                LocalVectorStore(path, 2, "model-v2")

    def test_interrupted_rebuild_leaves_previous_index_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalVectorStore(Path(tmp) / "index", 2, "model@revision")
            store.upsert([record("old", [1, 0])])
            original = store._atomic_commit
            store._atomic_commit = lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk"))
            with self.assertRaises(OSError):
                store.rebuild([record("new", [0, 1])])
            store._atomic_commit = original
            reopened = LocalVectorStore(Path(tmp) / "index", 2, "model@revision")
            self.assertEqual(reopened.health()["records"], 1)
            self.assertEqual(reopened.search(np.array([1, 0]), VectorScope(), 1)[0].evidence_id,
                             "old")


if __name__ == "__main__":
    unittest.main()

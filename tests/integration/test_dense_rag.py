"""Hybrid ranking logs and dependency-gated neural encoder tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
import numpy as np

from bpmn_adapt.retrieval.contracts import RetrievalMode, VectorRecord, VectorScope
from bpmn_adapt.retrieval.hybrid import HybridRetriever
from bpmn_adapt.retrieval.local_vector_store import LocalVectorStore
from bpmn_adapt.retrieval.service import HybridRAGService


class Encoder:
    model_key = "fake-neural@1"
    dimensions = 2
    def encode_queries(self, texts): return np.asarray([[1, 0] for _ in texts], dtype=np.float32)
    def encode_documents(self, texts):
        return np.asarray([[1, 0] if "permit" in text else [0, 1] for text in texts], dtype=np.float32)


class DenseRagTests(unittest.TestCase):
    def test_ablation_modes_log_candidates_filters_and_component_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalVectorStore(Path(tmp) / "vectors", 2, Encoder.model_key)
            records = [
                VectorRecord("semantic", "permit approval case", np.array([1, 0]),
                             {"process_id": "p", "operation": "REMOVE"}, True, Encoder.model_key),
                VectorRecord("lexical", "remove invoice activity", np.array([0, 1]),
                             {"process_id": "p", "operation": "REMOVE"}, True, Encoder.model_key),
            ]
            store.upsert(records)
            retriever = HybridRetriever(store, Encoder())
            for mode in RetrievalMode:
                result = retriever.retrieve("remove invoice", VectorScope("p", "REMOVE"),
                                            mode=mode, limit=2)
                self.assertEqual(result.log.mode, mode)
                self.assertEqual(result.log.filters["process_id"], "p")
                if mode is not RetrievalMode.NONE:
                    self.assertTrue(result.log.candidates)
                    self.assertTrue(all("final" in item.scores for item in result.log.candidates))

    def test_persistent_service_encodes_at_index_time_not_retrieval_time(self) -> None:
        class CountingEncoder(Encoder):
            def __init__(self): self.document_calls=0
            def encode_documents(self,texts):
                self.document_calls += 1
                return super().encode_documents(texts)
        class Database:
            rows=[{"evidence_id":"e","text":"permit removal","process_id":"p",
                   "operation":"REMOVE","source_version_id":"v","active":1,
                   "decision":"ACCEPT","metadata_json":"{}"}]
            def list_rag_cases(self,*args,**kwargs): return self.rows
            def save_retrieval_log(self,*args,**kwargs): self.logged=True
        with tempfile.TemporaryDirectory() as tmp:
            encoder=CountingEncoder()
            store=LocalVectorStore(Path(tmp)/"vectors",2,encoder.model_key)
            service=HybridRAGService(Database(),encoder,retriever=HybridRetriever(store,encoder),vector_store=store)
            self.assertEqual(service.index_existing(process_id="p"),1)
            calls=encoder.document_calls
            hits=service.retrieve("permit",process_id="p",operation="REMOVE",
                                  source_version_id="v",run_id="r")
            self.assertEqual(encoder.document_calls,calls)
            self.assertEqual(hits[0].evidence_id,"e")

    @unittest.skipUnless(importlib.util.find_spec("sentence_transformers"),
                         "SentenceTransformers/model external dependency unavailable")
    def test_real_sentence_transformer_encoder(self) -> None:
        from bpmn_adapt.retrieval.dense import SentenceTransformerEncoder
        encoder = SentenceTransformerEncoder("sentence-transformers/all-MiniLM-L6-v2")
        vectors = encoder.encode_documents(["approve request", "reject invoice"])
        self.assertEqual(vectors.shape[0], 2)
        self.assertGreater(vectors.shape[1], 100)


if __name__ == "__main__":
    unittest.main()

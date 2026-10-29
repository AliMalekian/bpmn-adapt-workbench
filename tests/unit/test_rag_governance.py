from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import unittest
import numpy as np

from bpmn_adapt.retrieval.governance import RagGovernance
from bpmn_adapt.retrieval.local_vector_store import LocalVectorStore


@dataclass
class Item:
    evidence_id: str
    text: str
    metadata: dict


class Encoder:
    model_key = "m@1"
    def encode_documents(self, texts): return np.asarray([[1, 0] for _ in texts], dtype=np.float32)


class Repository:
    def __init__(self): self.revoked = []
    def revoke_case(self, evidence_id, reason): self.revoked.append((evidence_id, reason))


class RagGovernanceTests(unittest.TestCase):
    def test_success_evidence_requires_approval_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalVectorStore(Path(tmp), 2, "m@1")
            governance = RagGovernance(Repository(), store, Encoder())
            with self.assertRaises(PermissionError):
                governance.index_approved([Item("bad", "candidate", {
                    "approval_status": "pending", "validation_status": "PASS"})])
            governance.index_approved([Item("good", "approved", {
                "approval_status": "approved", "validation_status": "PASS",
                "evidence_label": "positive"})])
            governance.revoke("good", "superseded")
            self.assertEqual(store.health()["records"], 1)
            self.assertFalse(store._records["good"].active)

    def test_negative_examples_require_an_explicit_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            governance = RagGovernance(Repository(), LocalVectorStore(Path(tmp), 2, "m@1"), Encoder())
            with self.assertRaises(PermissionError):
                governance.index_negative([Item("x", "failed", {})])
            governance.index_negative([Item("x", "failed", {"evidence_label": "negative"})])


if __name__ == "__main__": unittest.main()

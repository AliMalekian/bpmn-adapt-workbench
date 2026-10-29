"""Approval-gated indexing and reversible evidence governance."""
from __future__ import annotations


class RagGovernance:
    def __init__(self, repository, vector_store, encoder):
        self.repository, self.vector_store, self.encoder = repository, vector_store, encoder

    def index_approved(self, records):
        approved = [item for item in records if item.metadata.get("approval_status") == "approved"
                    and item.metadata.get("validation_status") == "PASS"]
        if len(approved) != len(records):
            raise PermissionError("Only approved and validated adaptations may enter success evidence")
        vectors = self.encoder.encode_documents([item.text for item in approved])
        from .contracts import VectorRecord
        self.vector_store.upsert([VectorRecord(item.evidence_id, item.text, vectors[index],
                                  item.metadata, True, self.encoder.model_key)
                                  for index, item in enumerate(approved)])

    def revoke(self, evidence_id, reason):
        self.repository.revoke_case(evidence_id, reason)
        self.vector_store.revoke(evidence_id, reason)

    def index_negative(self, records):
        if any(item.metadata.get("evidence_label") != "negative" for item in records):
            raise PermissionError("Negative evidence must be explicitly labeled")
        vectors = self.encoder.encode_documents([item.text for item in records])
        from .contracts import VectorRecord
        self.vector_store.upsert([VectorRecord(item.evidence_id, item.text, vectors[index],
                                  item.metadata, True, self.encoder.model_key)
                                  for index, item in enumerate(records)])

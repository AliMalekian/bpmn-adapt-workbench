"""Governed hybrid semantic and syntactic retrieval."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

from bpmn_adapt.domain.models import OperationType, RetrievedEvidence
from bpmn_adapt.llm.embedding import cosine_similarity


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\w-]+", text.casefold()))


def _lexical_score(query: str, text: str) -> float:
    q, t = _tokens(query), _tokens(text)
    return len(q & t) / len(q | t) if q and t else 0.0


class HybridRAGService:
    INDEX_VERSION = "hybrid-rag-v1"

    def __init__(self, database, embedding_client=None, default_mode: str = "hybrid",
                 *, retriever=None, vector_store=None):
        self.database = database
        self.embedding_client = embedding_client
        self.default_mode = default_mode
        self.retriever = retriever
        self.vector_store = vector_store

    @classmethod
    def from_settings(cls, database, settings):
        """Build the production neural/persistent retrieval stack from configuration."""
        from .dense import SentenceTransformerEncoder
        from .hybrid import HybridRetriever
        encoder = SentenceTransformerEncoder(
            settings.embedding_model, revision=settings.embedding_revision,
            device=settings.embedding_device, batch_size=settings.embedding_batch_size)
        if settings.vector_backend == "local":
            from .local_vector_store import LocalVectorStore
            store = LocalVectorStore(Path(settings.vector_path), encoder.dimensions,
                                     encoder.model_key)
        else:
            from .pgvector_store import PgVectorStore
            store = PgVectorStore(database.connection, encoder.dimensions, encoder.model_key)
            store.initialize()
        retriever = HybridRetriever(store, encoder, settings.rag_semantic_weight,
                                    settings.rag_syntactic_weight)
        return cls(database, encoder, settings.rag_mode, retriever=retriever,
                   vector_store=store)

    def retrieve(self, query: str, *, process_id: str, operation: str, source_version_id: str | None, run_id: str, mode: str | None = None, limit: int = 5) -> tuple[RetrievedEvidence, ...]:
        mode = mode or self.default_mode
        if mode not in {"none", "syntactic", "semantic", "hybrid"}:
            raise ValueError(f"Unsupported RAG mode: {mode}")
        filters = {"process_id": process_id, "operation": operation, "source_version_id": source_version_id, "active": True}
        rows = [] if mode == "none" else self.database.list_rag_cases(process_id, active_only=True, operation=operation, source_version_id=source_version_id)
        if not rows and mode != "none":
            if operation == "ADD":
                rows = self.database.list_rag_cases(process_id, active_only=True, operation="RE_ADD", source_version_id=source_version_id)
            elif operation == "MODIFY":
                rows = self.database.list_rag_cases(process_id, active_only=True, operation=None, source_version_id=source_version_id)
        if self.retriever is not None:
            return self._retrieve_persistent(query, rows, process_id, operation,
                                             source_version_id, run_id, mode, limit)
        query_embedding = self.embedding_client.embed(query)
        evidence: list[RetrievedEvidence] = []
        score_log: dict[str, dict[str, float]] = {}
        for row in rows:
            lexical = _lexical_score(query, row["text"])
            semantic = cosine_similarity(query_embedding, self.embedding_client.embed(row["text"]))
            if mode == "syntactic": final = lexical
            elif mode == "semantic": final = semantic
            else: final = 0.65 * semantic + 0.35 * lexical
            score_log[row["evidence_id"]] = {"semantic": semantic, "syntactic": lexical, "final": final}
            evidence.append(RetrievedEvidence(
                evidence_id=row["evidence_id"], process_id=row["process_id"],
                operation=OperationType(row["operation"]), text=row["text"], decision=row["decision"],
                semantic_score=semantic, syntactic_score=lexical, final_score=final,
                source_version_id=row["source_version_id"], active=bool(row["active"]),
                metadata=json.loads(row["metadata_json"] or "{}"),
            ))
        evidence.sort(key=lambda item: (-item.final_score, item.evidence_id))
        selected = tuple(evidence[:limit])
        retrieval_id = str(uuid.uuid4())
        self.database.save_retrieval_log(
            retrieval_id, run_id, hashlib.sha256(query.encode()).hexdigest(), filters,
            score_log, [item.evidence_id for item in selected], self.INDEX_VERSION,
        )
        return selected

    def index_existing(self, *, process_id: str, operation: str | None = None,
                       source_version_id: str | None = None) -> int:
        """Encode DB evidence during ingestion/indexing, never on the query path."""
        if self.vector_store is None:
            return 0
        from .contracts import VectorRecord
        rows = self.database.list_rag_cases(
            process_id, active_only=True, operation=operation,
            source_version_id=source_version_id)
        if not rows:
            return 0
        vectors = self.embedding_client.encode_documents([row["text"] for row in rows])
        records = []
        for index, row in enumerate(rows):
            metadata = json.loads(row["metadata_json"] or "{}")
            metadata.update({"process_id": row["process_id"],
                             "operation": row["operation"],
                             "source_version_id": row["source_version_id"]})
            records.append(VectorRecord(row["evidence_id"], row["text"], vectors[index],
                                         metadata, bool(row["active"]),
                                         self.embedding_client.model_key))
        self.vector_store.upsert(records)
        return len(records)

    def _retrieve_persistent(self, query, rows, process_id, operation,
                             source_version_id, run_id, mode, limit):
        from .contracts import RetrievalMode, VectorScope
        target_op = operation
        if operation == "ADD" and not any(r.get("operation") == "ADD" for r in rows):
            target_op = "RE_ADD"
        elif operation == "MODIFY" and not any(r.get("operation") == "MODIFY" for r in rows):
            target_op = None
        result = self.retriever.retrieve(
            query, VectorScope(process_id, target_op, source_version_id),
            mode=RetrievalMode(mode), limit=limit)
        by_id = {row["evidence_id"]: row for row in rows}
        selected_list = []
        for item in result.hits:
            row_match = by_id.get(item.evidence_id)
            if not row_match:
                continue
            sem_score = next((entry.scores["semantic"] for entry in result.log.candidates if entry.evidence_id == item.evidence_id), 0.0)
            syn_score = next((entry.scores["syntactic"] for entry in result.log.candidates if entry.evidence_id == item.evidence_id), 0.0)
            selected_list.append(RetrievedEvidence(
                item.evidence_id, process_id, OperationType(operation), item.text,
                row_match.get("decision", "UNKNOWN"),
                sem_score, syn_score, item.score, source_version_id, True, item.metadata
            ))
        selected = tuple(selected_list)
        score_log = {item.evidence_id: item.scores for item in result.log.candidates}
        self.database.save_retrieval_log(
            result.log.retrieval_id, run_id, result.log.query_hash,
            result.log.filters, score_log, [item.evidence_id for item in selected],
            result.log.fusion_version)
        return selected

    def index_approved(self, *, evidence_id: str, run_id: str, process_id: str, source_version_id: str, operation: str, text: str, decision: str, lineage: dict) -> None:
        """Index only through the database approval gate."""
        self.database.add_rag_case(evidence_id, run_id, process_id, source_version_id, operation, text, decision, json.dumps(lineage, sort_keys=True))
        if self.vector_store is not None:
            from .contracts import VectorRecord
            metadata = {**lineage, "process_id": process_id, "operation": operation,
                        "source_version_id": source_version_id,
                        "approval_status": "approved", "validation_status": "PASS",
                        "evidence_label": "positive"}
            vector = self.embedding_client.encode_documents([text])[0]
            self.vector_store.upsert([VectorRecord(evidence_id, text, vector, metadata,
                                                    True, self.embedding_client.model_key)])

    def revoke(self, evidence_id: str, reason: str) -> None:
        self.database.revoke_rag_case(evidence_id, reason)
        if self.vector_store is not None:
            self.vector_store.revoke(evidence_id, reason)

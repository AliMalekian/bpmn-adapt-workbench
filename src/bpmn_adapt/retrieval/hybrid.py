"""Versioned dense+BM25 fusion with ablation-complete ranking logs."""
from __future__ import annotations

import hashlib
import uuid

from .contracts import (RankedCandidate, RetrievalLog, RetrievalMode, RetrievalResult,
                        VectorHit, VectorScope)
from .lexical import bm25


class HybridRetriever:
    FUSION_VERSION = "weighted-fusion-v1"

    def __init__(self, vector_store, encoder, semantic_weight=.65, syntactic_weight=.35):
        self.store, self.encoder = vector_store, encoder
        self.semantic_weight, self.syntactic_weight = semantic_weight, syntactic_weight

    def retrieve(self, query, scope: VectorScope, *, mode=RetrievalMode.HYBRID, limit=5):
        mode = RetrievalMode(mode)
        semantic_hits = (() if mode in {RetrievalMode.NONE, RetrievalMode.SYNTACTIC}
                         else self.store.search(self.encoder.encode_queries([query])[0], scope, 10_000))
        # Exact local/pgvector stores expose scoped records through broad semantic search.
        corpus_hits = (self.store.list(scope)
                       if mode in {RetrievalMode.SYNTACTIC, RetrievalMode.HYBRID} else semantic_hits)
        documents = {item.evidence_id: item.text for item in corpus_hits}
        lexical = bm25(query, documents)
        semantic = {item.evidence_id: max(0.0, item.score) for item in semantic_hits}
        metadata = {item.evidence_id: item.metadata for item in corpus_hits or semantic_hits}
        texts = {item.evidence_id: item.text for item in corpus_hits or semantic_hits}
        identifiers = set(semantic) | set(lexical)
        candidates = []
        for evidence_id in identifiers:
            sem, syn = semantic.get(evidence_id, 0.0), lexical.get(evidence_id, 0.0)
            final = (0.0 if mode is RetrievalMode.NONE else syn if mode is RetrievalMode.SYNTACTIC
                     else sem if mode is RetrievalMode.SEMANTIC
                     else self.semantic_weight * sem + self.syntactic_weight * syn)
            candidates.append((evidence_id, final, sem, syn))
        candidates.sort(key=lambda item: (-item[1], item[0]))
        ranked = tuple(RankedCandidate(identifier, rank,
                         {"semantic": sem, "syntactic": syn, "final": final},
                         metadata.get(identifier, {}))
                       for rank, (identifier, final, sem, syn) in enumerate(candidates, 1))
        selected = tuple(VectorHit(identifier, texts.get(identifier, ""), final,
                                   metadata.get(identifier, {}))
                         for identifier, final, _, _ in candidates[:limit])
        log = RetrievalLog(str(uuid.uuid4()), hashlib.sha256(query.encode()).hexdigest(),
                           mode, scope.filters(), self.encoder.model_key,
                           self.FUSION_VERSION, ranked)
        return RetrievalResult(selected, log)

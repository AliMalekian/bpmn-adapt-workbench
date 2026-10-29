"""Standard labeled retrieval metrics for RAG evaluation."""
from __future__ import annotations

import math


def retrieval_metrics(ranked_ids, relevant_ids, k):
    ranked, relevant = list(ranked_ids)[:k], set(relevant_ids)
    hits = [1 if item in relevant else 0 for item in ranked]
    recall = sum(hits) / len(relevant) if relevant else 0.0
    reciprocal_rank = next((1.0 / index for index, hit in enumerate(hits, 1) if hit), 0.0)
    dcg = sum(hit / math.log2(index + 1) for index, hit in enumerate(hits, 1))
    ideal = sum(1 / math.log2(index + 1) for index in range(1, min(len(relevant), k) + 1))
    return {f"recall@{k}": recall, "mrr": reciprocal_rank,
            f"ndcg@{k}": dcg / ideal if ideal else 0.0}

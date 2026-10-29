"""Compatibility/test embeddings and similarity utilities.

Production neural encoding is implemented by
``retrieval.dense.SentenceTransformerEncoder``.  The hashing encoder in this
module is intentionally selected only by the explicit ``hash_test`` profile.
"""
from __future__ import annotations
import hashlib
import math
import re
from typing import Protocol


class EmbeddingClient(Protocol):
    model_id: str
    def embed(self, text: str) -> tuple[float, ...]: ...


class HashEmbeddingClient(EmbeddingClient):
    model_id = "hashing-v1"

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[\w-]+", text.casefold())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            position = int.from_bytes(digest[:4], "big") % self.dimensions
            # Signed hashing keeps collisions unbiased instead of making every
            # accidental collision look semantically positive.
            vector[position] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return tuple(x / norm for x in vector)


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right))

"""Pinned SentenceTransformers encoder with reproducibility metadata."""
from __future__ import annotations

import numpy as np


class SentenceTransformerEncoder:
    def __init__(self, model_name: str, *, revision: str = "main", device: str = "cpu",
                 batch_size: int = 32):
        from sentence_transformers import SentenceTransformer
        self.model_name, self.revision, self.device = model_name, revision, device
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name, revision=revision, device=device)
        self.dimensions = int(self.model.get_sentence_embedding_dimension())
        self.model_key = f"{model_name}@{revision}:{device}:normalized"

    def encode_documents(self, texts):
        return self._encode(texts, "document")

    def encode_queries(self, texts):
        return self._encode(texts, "query")

    def _encode(self, texts, prompt_name):
        values = self.model.encode(list(texts), batch_size=self.batch_size,
                                   normalize_embeddings=True, convert_to_numpy=True,
                                   show_progress_bar=False)
        return np.asarray(values, dtype=np.float32)

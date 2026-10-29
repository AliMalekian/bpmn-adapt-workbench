"""Dependency-free BM25 lexical scorer."""
from __future__ import annotations

from collections import Counter
import math
import re


def tokens(text): return re.findall(r"[\w-]+", text.casefold())


def bm25(query: str, documents: dict[str, str], k1=1.5, b=0.75):
    terms = tokens(query); tokenized = {key: tokens(text) for key, text in documents.items()}
    n = len(tokenized) or 1; avgdl = sum(map(len, tokenized.values())) / n or 1
    document_frequency = Counter(term for term in set(terms)
                                 for words in tokenized.values() if term in words)
    scores = {}
    for key, words in tokenized.items():
        frequencies, score = Counter(words), 0.0
        for term in terms:
            df = document_frequency[term]
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            tf = frequencies[term]
            score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(words) / avgdl)) if tf else 0
        scores[key] = score
    maximum = max(scores.values(), default=0) or 1
    return {key: value / maximum for key, value in scores.items()}

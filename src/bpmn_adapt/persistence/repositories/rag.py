"""Advisory RAG repository facade; deliberately excludes core-fact writes."""
from __future__ import annotations


class RelationalRagRepository:
    def __init__(self, database):
        self._database = database

    def add_approved_case(self, *args, **kwargs):
        return self._database.add_rag_case(*args, **kwargs)

    def list_cases(self, *args, **kwargs):
        return self._database.list_rag_cases(*args, **kwargs)

    def revoke_case(self, *args, **kwargs):
        return self._database.revoke_rag_case(*args, **kwargs)

    def has_case(self, *args, **kwargs):
        return self._database.has_rag_case(*args, **kwargs)

    def save_retrieval_log(self, *args, **kwargs):
        return self._database.save_retrieval_log(*args, **kwargs)

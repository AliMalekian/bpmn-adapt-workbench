"""Utility script to purge all live-accumulated negative RAG experiences,
reverting the RAG memory back to the clean positive-only baseline.
"""
from pathlib import Path
from bpmn_adapt.persistence.sqlite import SqliteDatabase
from bpmn_adapt.retrieval.local_vector_store import LocalVectorStore
from bpmn_adapt.retrieval.service import HybridRAGService
from bpmn_adapt.config import Settings

settings = Settings()
db = SqliteDatabase(settings.database_url)
v_store = LocalVectorStore(settings.output_root / "vector_index", 384, settings.embedding_model) if (settings.output_root / "vector_index").is_dir() else None

rag = HybridRAGService(
    database=db,
    embedding_client=None,
    vector_store=v_store,
)

purged = rag.purge_negative_experiences()
print(f"Purged {purged} live negative experiences from vector index and database.")
print("RAG memory successfully reverted to clean positive state.")

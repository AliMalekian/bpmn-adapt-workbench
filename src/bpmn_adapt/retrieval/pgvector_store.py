"""PostgreSQL/pgvector implementation of the vector-store contract."""
from __future__ import annotations

import json
import numpy as np
from .contracts import VectorHit


class PgVectorStore:
    def __init__(self, connection, dimensions: int, model_key: str,
                 table="rag_vectors"):
        self.connection, self.dimensions, self.model_key, self.table = connection, dimensions, model_key, table

    def initialize(self):
        with self.connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(f'''CREATE TABLE IF NOT EXISTS {self.table} (
                evidence_id TEXT PRIMARY KEY, text TEXT NOT NULL, embedding vector({self.dimensions}) NOT NULL,
                metadata JSONB NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE, model_key TEXT NOT NULL)''')
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {self.table}_hnsw ON {self.table} USING hnsw (embedding vector_cosine_ops)")
        self.connection.commit()
        from pgvector.psycopg import register_vector
        register_vector(self.connection)

    def upsert(self, records):
        with self.connection.cursor() as cursor:
            for item in records:
                if item.model_key != self.model_key: raise ValueError("Vector model key mismatch")
                cursor.execute(f'''INSERT INTO {self.table}(evidence_id,text,embedding,metadata,active,model_key)
                    VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(evidence_id) DO UPDATE SET
                    text=excluded.text,embedding=excluded.embedding,metadata=excluded.metadata,
                    active=excluded.active,model_key=excluded.model_key''',
                    (item.evidence_id, item.text, np.asarray(item.vector, dtype=np.float32),
                     json.dumps(item.metadata), item.active, item.model_key))
        self.connection.commit()

    def search(self, query, scope, limit):
        filters, values = ["model_key=%s"], [self.model_key]
        for key, value in scope.filters().items():
            if key == "active_only":
                if value: filters.append("active=TRUE")
            else: filters.append(f"metadata->>%s=%s"); values.extend([key, str(value)])
        sql = f'''SELECT evidence_id,text,metadata,1-(embedding <=> %s::vector) AS score
                  FROM {self.table} WHERE {' AND '.join(filters)} ORDER BY embedding <=> %s::vector LIMIT %s'''
        # Vector appears in ORDER and score; insert it at both parameter positions.
        vector = np.asarray(query, dtype=np.float32)
        params = [vector, *values, vector, limit]
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return tuple(VectorHit(row[0], row[1], float(row[3]), row[2]) for row in cursor.fetchall())

    def revoke(self, evidence_id, reason):
        with self.connection.cursor() as cursor:
            cursor.execute(f"UPDATE {self.table} SET active=FALSE, metadata=metadata || %s::jsonb WHERE evidence_id=%s",
                           (json.dumps({"revocation_reason": reason}), evidence_id))
        self.connection.commit()

    def list(self, scope):
        filters, params = ["model_key=%s"], [self.model_key]
        for key, value in scope.filters().items():
            if key == "active_only":
                if value: filters.append("active=TRUE")
            else: filters.append("metadata->>%s=%s"); params.extend([key, str(value)])
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT evidence_id,text,metadata FROM {self.table} WHERE {' AND '.join(filters)}", params)
            return tuple(VectorHit(row[0], row[1], 0.0, row[2]) for row in cursor.fetchall())

    def rebuild(self, records):
        with self.connection.cursor() as cursor: cursor.execute(f"TRUNCATE {self.table}")
        self.upsert(records)

    def health(self):
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT count(*) FROM {self.table} WHERE model_key=%s", (self.model_key,))
            return {"status": "READY", "records": cursor.fetchone()[0], "backend": "pgvector-hnsw"}

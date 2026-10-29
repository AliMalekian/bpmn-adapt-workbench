"""Crash-safe persistent exact vector store for offline/reproducible runs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import numpy as np

from .contracts import VectorHit, VectorRecord, VectorScope


class LocalVectorStore:
    INDEX_VERSION = "local-exact-v1"

    def __init__(self, path: Path, dimensions: int, model_key: str):
        self.path, self.dimensions, self.model_key = Path(path), int(dimensions), model_key
        self.manifest_path = self.path / "manifest.json"
        self.data_path = self.path / "vectors.npz"
        self._lock = threading.RLock()
        self._records: dict[str, VectorRecord] = {}
        if self.manifest_path.exists():
            self._load()

    def upsert(self, records):
        with self._lock:
            updated = dict(self._records)
            for record in records:
                self._validate(record); updated[record.evidence_id] = record
            self._atomic_commit(updated); self._records = updated

    def rebuild(self, records):
        updated = {}
        for record in records:
            self._validate(record); updated[record.evidence_id] = record
        with self._lock:
            self._atomic_commit(updated); self._records = updated

    def revoke(self, evidence_id, reason):
        with self._lock:
            if evidence_id not in self._records: return
            old = self._records[evidence_id]
            metadata = {**old.metadata, "revocation_reason": reason}
            updated = {**self._records, evidence_id: VectorRecord(
                old.evidence_id, old.text, old.vector, metadata, False, old.model_key)}
            self._atomic_commit(updated); self._records = updated

    def search(self, query, scope: VectorScope, limit: int):
        query = np.asarray(query, dtype=np.float32).reshape(-1)
        if query.size != self.dimensions: raise ValueError("Query dimensions mismatch")
        norm = np.linalg.norm(query) or 1.0; query = query / norm
        hits = []
        for item in self._records.values():
            if scope.active_only and not item.active: continue
            if any(value is not None and item.metadata.get(key) != value
                   for key, value in scope.filters().items() if key != "active_only"): continue
            vector = item.vector / (np.linalg.norm(item.vector) or 1.0)
            hits.append(VectorHit(item.evidence_id, item.text, float(np.dot(query, vector)),
                                  dict(item.metadata)))
        hits.sort(key=lambda item: (-item.score, item.evidence_id))
        return tuple(hits[:limit])

    def list(self, scope: VectorScope):
        hits = []
        for item in self._records.values():
            if scope.active_only and not item.active: continue
            if any(value is not None and item.metadata.get(key) != value
                   for key, value in scope.filters().items() if key != "active_only"): continue
            hits.append(VectorHit(item.evidence_id, item.text, 0.0, dict(item.metadata)))
        return tuple(sorted(hits, key=lambda item: item.evidence_id))

    def health(self):
        return {"status": "READY", "backend": self.INDEX_VERSION,
                "records": len(self._records), "model_key": self.model_key,
                "dimensions": self.dimensions}

    def _validate(self, record):
        if record.model_key != self.model_key: raise ValueError("Vector model key mismatch")
        if np.asarray(record.vector).size != self.dimensions: raise ValueError("Vector dimensions mismatch")

    def _atomic_commit(self, records):
        self.path.mkdir(parents=True, exist_ok=True)
        identifiers = sorted(records)
        vectors = np.vstack([records[key].vector for key in identifiers]) if identifiers else np.empty((0, self.dimensions))
        metadata = [{"evidence_id": key, "text": records[key].text,
                     "metadata": records[key].metadata, "active": records[key].active,
                     "model_key": records[key].model_key} for key in identifiers]
        with tempfile.TemporaryDirectory(dir=self.path) as tmp:
            tmp_path = Path(tmp); data = tmp_path / "vectors.npz"; manifest = tmp_path / "manifest.json"
            np.savez_compressed(data, vectors=vectors)
            content_hash = hashlib.sha256(data.read_bytes()).hexdigest()
            final_data = self.path / f"vectors.{content_hash}.npz"
            manifest.write_text(json.dumps({"index_version": self.INDEX_VERSION,
                "model_key": self.model_key, "dimensions": self.dimensions,
                "content_checksum": content_hash, "data_file": final_data.name,
                "records": metadata}, sort_keys=True), encoding="utf-8")
            if not final_data.exists():
                os.replace(data, final_data)
            os.replace(manifest, self.manifest_path)
            self.data_path = final_data

    def _load(self):
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if manifest["model_key"] != self.model_key: raise ValueError("Persisted vector model key mismatch")
        if int(manifest["dimensions"]) != self.dimensions: raise ValueError("Persisted vector dimensions mismatch")
        self.data_path = self.path / manifest["data_file"]
        if hashlib.sha256(self.data_path.read_bytes()).hexdigest() != manifest["content_checksum"]:
            raise ValueError("Vector index checksum mismatch")
        vectors = np.load(self.data_path, allow_pickle=False)["vectors"]
        self._records = {item["evidence_id"]: VectorRecord(
            item["evidence_id"], item["text"], vectors[index], item["metadata"],
            bool(item["active"]), item["model_key"])
            for index, item in enumerate(manifest["records"])}

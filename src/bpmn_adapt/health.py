"""Structured readiness probes for offline and opt-in live capabilities."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import sqlite3
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import CapabilityStatus, Settings


class UnauthorizedProbe(PermissionError):
    pass


class MissingDependencyProbe(ImportError):
    pass


class ProbeDependencies:
    """Real boundary operations, replaceable as one unit in unit tests."""

    def probe_database(self, settings: Settings) -> dict[str, str | None]:
        if settings.database_url.startswith("sqlite:///"):
            raw = settings.database_url.removeprefix("sqlite:///")
            connection = sqlite3.connect(":memory:" if raw == ":memory:" else raw)
            try:
                version = connection.execute("SELECT sqlite_version()").fetchone()[0]
            finally:
                connection.close()
            return {"server_version": version, "pgvector_version": None}
        try:
            import psycopg
        except ImportError as exc:
            raise MissingDependencyProbe("psycopg is not installed") from exc
        with psycopg.connect(settings.database_url, connect_timeout=max(1, int(settings.timeout_seconds))) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('server_version')")
                server = cursor.fetchone()[0]
                cursor.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
                row = cursor.fetchone()
        return {"server_version": server, "pgvector_version": None if row is None else row[0]}

    def probe_model(self, settings: Settings) -> str:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise MissingDependencyProbe("sentence-transformers is not installed") from exc
        try:
            model = SentenceTransformer(
                settings.embedding_model,
                revision=settings.embedding_revision,
                device=settings.embedding_device,
                local_files_only=True,
            )
        except OSError as exc:
            raise FileNotFoundError("embedding model is not cached") from exc
        return f"{settings.embedding_model}@{settings.embedding_revision}:{model.get_sentence_embedding_dimension()}"

    def probe_http(self, url: str, headers: Mapping[str, str], timeout: float) -> dict:
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read(1_000_000)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise UnauthorizedProbe(f"HTTP {exc.code}") from exc
            raise
        return json.loads(body.decode("utf-8")) if body else {}


def _failure(name: str, exc: BaseException) -> CapabilityStatus:
    if isinstance(exc, UnauthorizedProbe):
        return CapabilityStatus(name, "UNAUTHORIZED", "service rejected configured credentials")
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return CapabilityStatus(name, "TIMEOUT", "service did not respond before the configured timeout")
    if isinstance(exc, ConnectionRefusedError):
        return CapabilityStatus(name, "REFUSED", "service endpoint refused the connection")
    if isinstance(exc, URLError):
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return CapabilityStatus(name, "TIMEOUT", "service did not respond before the configured timeout")
        return CapabilityStatus(name, "REFUSED", "service endpoint is unreachable")
    if isinstance(exc, FileNotFoundError):
        return CapabilityStatus(name, "MISSING_MODEL", "configured dense model is not cached locally")
    if isinstance(exc, (MissingDependencyProbe, ImportError)):
        return CapabilityStatus(name, "MISSING_DEPENDENCY", "required adapter dependency is not installed")
    return CapabilityStatus(name, "ERROR", f"probe failed with {type(exc).__name__}")


def probe_all(
    settings: Settings, dependencies: ProbeDependencies | None = None
) -> tuple[CapabilityStatus, ...]:
    """Probe configured capabilities without converting failures into success."""
    deps = dependencies or ProbeDependencies()
    statuses: dict[str, CapabilityStatus] = {}

    try:
        database_info = deps.probe_database(settings)
        postgres = settings.database_url.startswith(("postgresql://", "postgres://"))
        statuses["database"] = CapabilityStatus(
            "database", "READY_LIVE" if postgres else "READY_OFFLINE",
            f"database server {database_info.get('server_version', 'unknown')}",
        )
        if settings.vector_backend == "pgvector":
            pgvector_version = database_info.get("pgvector_version")
            statuses["vector_store"] = CapabilityStatus(
                "vector_store",
                "READY_LIVE" if pgvector_version else "INCOMPATIBLE_VERSION",
                f"pgvector {pgvector_version}" if pgvector_version else "pgvector extension is not installed",
            )
        else:
            statuses["vector_store"] = CapabilityStatus(
                "vector_store", "READY_OFFLINE", f"local index at {settings.vector_path}")
    except BaseException as exc:
        statuses["database"] = _failure("database", exc)
        statuses["vector_store"] = (
            _failure("vector_store", exc) if settings.vector_backend == "pgvector"
            else CapabilityStatus("vector_store", "READY_OFFLINE", f"local index at {settings.vector_path}")
        )

    try:
        model_identity = deps.probe_model(settings)
        statuses["embedding"] = CapabilityStatus("embedding", "READY_OFFLINE", model_identity)
    except BaseException as exc:
        statuses["embedding"] = _failure("embedding", exc)

    if settings.llm_mode == "mock":
        statuses["llm"] = CapabilityStatus("llm", "READY_OFFLINE", "deterministic mock adapter")
    else:
        try:
            deps.probe_http(
                settings.llm_base_url.rstrip("/") + "/models",
                {"Authorization": f"Bearer {settings.llm_api_key}"}, settings.timeout_seconds)
            statuses["llm"] = CapabilityStatus("llm", "READY_LIVE", "OpenAI-compatible endpoint responded")
        except BaseException as exc:
            statuses["llm"] = _failure("llm", exc)

    if settings.engine_mode == "disabled":
        statuses["engine"] = CapabilityStatus("engine", "DISABLED", "workflow engine is disabled")
    elif settings.engine_mode == "dry_run":
        statuses["engine"] = CapabilityStatus("engine", "READY_OFFLINE", "dry-run adapter")
    else:
        try:
            deps.probe_http(
                settings.engine_base_url.rstrip("/") + "/v2/topology", {},
                settings.engine_timeout_seconds)
            statuses["engine"] = CapabilityStatus("engine", "READY_LIVE", "Camunda topology endpoint responded")
        except BaseException as exc:
            statuses["engine"] = _failure("engine", exc)

    return tuple(statuses[name] for name in ("database", "vector_store", "embedding", "llm", "engine"))

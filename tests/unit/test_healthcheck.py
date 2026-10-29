"""Readiness probes distinguish external failure modes without overclaiming."""
from __future__ import annotations

import unittest

from bpmn_adapt.config import Settings
from bpmn_adapt.health import ProbeDependencies, UnauthorizedProbe, probe_all


class FakeDependencies(ProbeDependencies):
    def __init__(self, *, database=None, model=None, http=None):
        self.database_result = database if database is not None else {
            "server_version": "16.4", "pgvector_version": "0.8.0"
        }
        self.model_result = model if model is not None else "cached-revision"
        self.http_result = http if http is not None else {"version": "8.8.37"}

    def probe_database(self, settings):
        if isinstance(self.database_result, BaseException):
            raise self.database_result
        return self.database_result

    def probe_model(self, settings):
        if isinstance(self.model_result, BaseException):
            raise self.model_result
        return self.model_result

    def probe_http(self, url, headers, timeout):
        if isinstance(self.http_result, BaseException):
            raise self.http_result
        return self.http_result


class HealthCheckTests(unittest.TestCase):
    def test_ready_offline_profile(self) -> None:
        settings = Settings(engine_mode="dry_run")
        statuses = {item.name: item for item in probe_all(settings, FakeDependencies())}
        self.assertEqual(statuses["database"].status, "READY_OFFLINE")
        self.assertEqual(statuses["embedding"].status, "READY_OFFLINE")
        self.assertEqual(statuses["vector_store"].status, "READY_OFFLINE")
        self.assertEqual(statuses["engine"].status, "READY_OFFLINE")

    def test_connection_refused_is_not_reported_as_generic_success(self) -> None:
        settings = Settings(database_url="postgresql://localhost/research")
        statuses = {item.name: item for item in probe_all(
            settings, FakeDependencies(database=ConnectionRefusedError("refused")))}
        self.assertEqual(statuses["database"].status, "REFUSED")

    def test_unauthorized_and_timeout_are_distinct(self) -> None:
        settings = Settings(llm_mode="live", llm_api_key="secret")
        unauthorized = {item.name: item for item in probe_all(
            settings, FakeDependencies(http=UnauthorizedProbe("401")))}
        timed_out = {item.name: item for item in probe_all(
            settings, FakeDependencies(http=TimeoutError("slow")))}
        self.assertEqual(unauthorized["llm"].status, "UNAUTHORIZED")
        self.assertEqual(timed_out["llm"].status, "TIMEOUT")

    def test_missing_dense_model_is_blocked_external(self) -> None:
        statuses = {item.name: item for item in probe_all(
            Settings(), FakeDependencies(model=FileNotFoundError("not cached")))}
        self.assertEqual(statuses["embedding"].status, "MISSING_MODEL")

    def test_missing_pgvector_extension_is_incompatible(self) -> None:
        settings = Settings(
            database_url="postgresql://localhost/research", vector_backend="pgvector")
        statuses = {item.name: item for item in probe_all(
            settings, FakeDependencies(database={
                "server_version": "16.4", "pgvector_version": None}))}
        self.assertEqual(statuses["database"].status, "READY_LIVE")
        self.assertEqual(statuses["vector_store"].status, "INCOMPATIBLE_VERSION")


if __name__ == "__main__":
    unittest.main()

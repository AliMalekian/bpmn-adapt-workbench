"""Authoritative repository facade; deliberately excludes RAG mutation."""
from __future__ import annotations


class RelationalCoreRepository:
    def __init__(self, database):
        self._database = database

    def upsert_process(self, *args, **kwargs): return self._database.upsert_process(*args, **kwargs)
    def get_process(self, *args, **kwargs): return self._database.get_process(*args, **kwargs)
    def get_version(self, *args, **kwargs): return self._database.get_version(*args, **kwargs)
    def save_process_version(self, *args, **kwargs): return self._database.save_process_version(*args, **kwargs)
    def get_latest_version(self, *args, **kwargs): return self._database.get_latest_version(*args, **kwargs)
    def get_rules(self, *args, **kwargs): return self._database.get_rules(*args, **kwargs)
    def get_resources(self, *args, **kwargs): return self._database.get_resources(*args, **kwargs)
    def get_states(self, *args, **kwargs): return self._database.get_states(*args, **kwargs)
    def create_run(self, *args, **kwargs): return self._database.create_run(*args, **kwargs)
    def update_run_status(self, *args, **kwargs): return self._database.update_run_status(*args, **kwargs)
    def get_run(self, *args, **kwargs): return self._database.get_run(*args, **kwargs)
    def append_event(self, *args, **kwargs): return self._database.append_event(*args, **kwargs)
    def save_request(self, *args, **kwargs): return self._database.save_request(*args, **kwargs)
    def save_decision(self, *args, **kwargs): return self._database.save_decision(*args, **kwargs)
    def save_candidate(self, *args, **kwargs): return self._database.save_candidate(*args, **kwargs)
    def save_experiment(self, *args, **kwargs): return self._database.save_experiment(*args, **kwargs)

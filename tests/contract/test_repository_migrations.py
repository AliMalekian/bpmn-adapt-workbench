"""Contract tests for idempotent, data-preserving schema migrations."""
from __future__ import annotations

import sqlite3
import unittest

from bpmn_adapt.persistence.base import SCHEMA
from bpmn_adapt.persistence.migrator import MigrationRunner
from bpmn_adapt.persistence.sqlite import SQLiteDatabase


class RepositoryMigrationTests(unittest.TestCase):
    def test_upgrade_preserves_existing_data_and_is_idempotent(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        for statement in SCHEMA:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO processes(process_id,folder,name,narrative) VALUES(?,?,?,?)",
            ("legacy-process", "legacy-folder", "Legacy", "preserve me"),
        )
        connection.execute(
            "INSERT INTO runs(run_id,process_id,config_fingerprint,status) VALUES(?,?,?,?)",
            ("legacy-run", "legacy-process", "fingerprint", "approved"),
        )
        connection.commit()

        first = MigrationRunner().upgrade(connection, "sqlite")
        second = MigrationRunner().upgrade(connection, "sqlite")

        row = connection.execute(
            "SELECT narrative FROM processes WHERE process_id='legacy-process'"
        ).fetchone()
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual(row[0], "preserve me")
        self.assertEqual(first.applied_versions, ("0001_existing_schema", "0002_defense_schema"))
        self.assertEqual(second.applied_versions, ())
        self.assertEqual([item[0] for item in versions], list(first.applied_versions))

    def test_defense_schema_contains_every_evidence_domain(self) -> None:
        database = SQLiteDatabase(":memory:")
        report = database.initialize()
        expected = {
            "process_instances", "temporal_facts", "planner_runs", "planner_states",
            "temporal_plans", "validation_reports", "engine_deployments",
            "engine_migrations", "embedding_manifests", "experiment_observations",
            "approvals", "evidence_artifacts",
        }
        rows = database.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {row[0] for row in rows}

        self.assertTrue(expected <= names, expected - names)
        self.assertEqual(report.current_version, "0002_defense_schema")
        self.assertEqual(database.health().status, "READY")
        self.assertEqual(database.health().schema_version, "0002_defense_schema")
        database.close()

    def test_each_migration_is_atomic_on_failure(self) -> None:
        connection = sqlite3.connect(":memory:")
        runner = MigrationRunner(migrations=(
            ("0001_ok", ("CREATE TABLE durable(id TEXT PRIMARY KEY)",)),
            ("0002_bad", (
                "CREATE TABLE must_rollback(id TEXT PRIMARY KEY)",
                "THIS IS NOT SQL",
            )),
        ))

        with self.assertRaises(sqlite3.DatabaseError):
            runner.upgrade(connection, "sqlite")

        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        versions = {
            row[0] for row in connection.execute("SELECT version FROM schema_migrations")
        }
        self.assertIn("durable", tables)
        self.assertNotIn("must_rollback", tables)
        self.assertEqual(versions, {"0001_ok"})


if __name__ == "__main__":
    unittest.main()

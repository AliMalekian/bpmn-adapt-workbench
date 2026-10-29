"""Opt-in migration contract against a real disposable PostgreSQL DB."""
from __future__ import annotations

import os
import unittest

from bpmn_adapt.persistence import create_database


@unittest.skipUnless(
    os.environ.get("ADAPT_TEST_POSTGRES_URL"),
    "ADAPT_TEST_POSTGRES_URL is required for the live PostgreSQL migration gate",
)
class PostgreSQLMigrationIntegrationTests(unittest.TestCase):
    def test_upgrade_is_idempotent_and_reports_ready(self) -> None:
        database = create_database(os.environ["ADAPT_TEST_POSTGRES_URL"])
        try:
            first = database.initialize()
            second = database.initialize()
            self.assertIsNotNone(first.current_version)
            self.assertEqual(second.applied_versions, ())
            self.assertEqual(database.health().status, "READY")
        finally:
            database.close()


if __name__ == "__main__":
    unittest.main()

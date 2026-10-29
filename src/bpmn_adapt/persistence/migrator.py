"""Small DB-API migration runner shared by SQLite and PostgreSQL."""
from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from typing import Iterable, Sequence


@dataclass(frozen=True)
class MigrationReport:
    applied_versions: tuple[str, ...]
    current_version: str | None


def _split_sql(script: str) -> tuple[str, ...]:
    """Split project-controlled migration SQL into executable statements."""
    statements = []
    for part in script.split(";"):
        lines = [line for line in part.splitlines() if not line.lstrip().startswith("--")]
        statement = "\n".join(lines).strip()
        if statement:
            statements.append(statement)
    return tuple(statements)


def _bundled_migrations() -> tuple[tuple[str, tuple[str, ...]], ...]:
    root = files("bpmn_adapt.persistence.migrations")
    result = []
    for resource in sorted(root.iterdir(), key=lambda item: item.name):
        if resource.name.endswith(".sql"):
            result.append((resource.name[:-4], _split_sql(resource.read_text(encoding="utf-8"))))
    return tuple(result)


class MigrationRunner:
    """Apply ordered migrations once, committing each version atomically."""

    def __init__(self, migrations: Sequence[tuple[str, Sequence[str]]] | None = None):
        source = migrations if migrations is not None else _bundled_migrations()
        self.migrations = tuple((version, tuple(statements)) for version, statements in source)

    def upgrade(self, connection, dialect: str) -> MigrationReport:
        if dialect not in {"sqlite", "postgresql"}:
            raise ValueError(f"Unsupported migration dialect: {dialect}")
        cursor = connection.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        if dialect == "postgresql":
            cursor.execute("CREATE SCHEMA IF NOT EXISTS core")
            cursor.execute("CREATE SCHEMA IF NOT EXISTS rag")
        connection.commit()

        cursor = connection.cursor()
        cursor.execute("SELECT version FROM schema_migrations")
        applied = {row[0] if not isinstance(row, dict) else row["version"] for row in cursor.fetchall()}
        new_versions: list[str] = []
        placeholder = "?" if dialect == "sqlite" else "%s"
        for version, statements in self.migrations:
            if version in applied:
                continue
            try:
                cursor = connection.cursor()
                # SQLite does not automatically open a transaction for DDL.
                # An explicit boundary ensures a failed multi-statement
                # migration leaves neither partial tables nor a ledger row.
                cursor.execute("BEGIN")
                for statement in statements:
                    cursor.execute(statement)
                cursor.execute(
                    f"INSERT INTO schema_migrations(version) VALUES({placeholder})", (version,)
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            new_versions.append(version)
            applied.add(version)

        current = max(applied) if applied else None
        return MigrationReport(tuple(new_versions), current)

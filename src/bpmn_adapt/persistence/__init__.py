"""Database factory; SQLite is built in and PostgreSQL is optional."""
from __future__ import annotations

from .repositories import ApprovalRequired, DatabaseConfigurationError


def create_database(url: str):
    if url.startswith("sqlite:///"):
        from .sqlite import SQLiteDatabase
        return SQLiteDatabase(url.removeprefix("sqlite:///"))
    if url.startswith(("postgresql://", "postgres://")):
        try:
            from .postgres import PostgreSQLDatabase
            return PostgreSQLDatabase(url)
        except ImportError as exc:
            raise DatabaseConfigurationError("PostgreSQL support requires the optional psycopg dependency") from exc
    raise DatabaseConfigurationError(f"Unsupported database URL: {url}")


__all__ = ["create_database", "ApprovalRequired", "DatabaseConfigurationError"]


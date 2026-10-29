"""PostgreSQL implementation using the same repositories as SQLite."""
from __future__ import annotations
import psycopg
from psycopg.rows import dict_row
from .base import RelationalDatabase


class PostgreSQLDatabase(RelationalDatabase):
    placeholder = "%s"
    dialect = "postgresql"

    def __init__(self, url: str):
        super().__init__(psycopg.connect(url, row_factory=dict_row))

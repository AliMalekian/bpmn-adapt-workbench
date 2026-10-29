"""SQLite implementation of the repository boundary."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from .base import RelationalDatabase


class SQLiteDatabase(RelationalDatabase):
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        super().__init__(connection)


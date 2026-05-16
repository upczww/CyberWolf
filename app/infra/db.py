from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def initialize_database(path: Path, schema_path: Path) -> None:
    conn = connect_database(path)
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()

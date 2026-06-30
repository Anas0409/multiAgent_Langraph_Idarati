"""SQLite connection manager — single point of access for the entire project."""

import sqlite3
import os
from contextlib import contextmanager

_DB_PATH = None


def get_db_path() -> str:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = os.environ.get(
            "IDARATI_DB_PATH",
            os.path.join(os.path.dirname(__file__), "idarati.db"),
        )
    return _DB_PATH


def set_db_path(path: str) -> None:
    global _DB_PATH
    _DB_PATH = path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def close_all():
    pass

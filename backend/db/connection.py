"""SQLite connection management for Politerate."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

BACKEND_DIR = Path(__file__).parent.parent.resolve()
DB_PATH = BACKEND_DIR / "data" / "politerate.db"
SCHEMA_PATH = BACKEND_DIR / "db" / "schema.sql"


def init_db() -> None:
    """Create database file and tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False,)
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()
    
    print(f"Database initialized at: {DB_PATH}")


def get_connection() -> sqlite3.Connection:
    """Create a new connection with row factory set up for dict-like access."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # lets you access columns by name
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    """Context manager for database connections. Use in FastAPI dependencies."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
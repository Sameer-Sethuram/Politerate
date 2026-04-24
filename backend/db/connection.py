"""
backend/db/connection.py

SQLite connection + init. Schema lives in `schema.sql` (Sarah's convention).
Mirrors her `backend/db/connection.py` pattern.
"""

import logging
import sqlite3
from pathlib import Path

from backend.config import DB_PATH

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_db_path() -> str:
    return str(DB_PATH)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_ARTICLE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_url_hash ON articles(url_hash);
CREATE INDEX IF NOT EXISTS idx_articles_bias ON articles(bias_label);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(analysis_status);

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title, text,
    content=articles,
    content_rowid=id
);
"""


def init_db() -> None:
    """Create tables from schema.sql, apply column migrations, then create
    indexes + FTS (in that order — indexes can reference columns only
    added by the migration pass).
    """
    logger.info("Initializing database...")
    conn = get_connection()
    cursor = conn.cursor()

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    cursor.executescript(schema_sql)

    _apply_column_migrations(cursor)

    cursor.executescript(_ARTICLE_INDEXES_SQL)

    conn.commit()
    conn.close()
    logger.info("Database initialized")


def _apply_column_migrations(cursor) -> None:
    """Add columns to existing articles tables that were defined in earlier
    schemas. Non-destructive — existing rows get NULL / default values.
    """
    cursor.execute("PRAGMA table_info(articles)")
    existing = {row[1] for row in cursor.fetchall()}

    migrations = [
        ("url_hash",                "TEXT"),
        ("author",                  "TEXT"),
        ("published_at",            "TIMESTAMP"),
        ("word_count",              "INTEGER"),
        ("analysis_json",           "TEXT"),
        ("article_json",            "TEXT"),
        ("bias_label",              "TEXT"),
        ("dominant_emotion",        "TEXT"),
        ("subjectivity_ratio",      "REAL"),
        ("analysis_model_version",  "TEXT"),
        ("analyzed_at",             "TIMESTAMP"),
        ("analysis_status",         "TEXT DEFAULT 'pending'"),
        ("summary",                 "TEXT"),
        ("summary_model_version",   "TEXT"),
        ("summarized_at",           "TIMESTAMP"),
        ("source_type",             "TEXT DEFAULT 'scraped'"),
    ]

    for col, coltype in migrations:
        if col not in existing:
            try:
                cursor.execute(f"ALTER TABLE articles ADD COLUMN {col} {coltype}")
                logger.info(f"Added column articles.{col}")
            except sqlite3.OperationalError as e:
                logger.warning(f"Could not add column {col}: {e}")

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


# Seconds a statement waits for another connection's lock before raising
# "database is locked". sqlite3's default is 5, too short while the hourly
# pipeline commits large batches and page requests read concurrently.
BUSY_TIMEOUT_SECONDS = 30


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=BUSY_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    # Safe with WAL (set in init_db): commits skip an fsync, and a crash can
    # lose at most the last transaction, never corrupt the database.
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


_ARTICLE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_url_hash ON articles(url_hash);
CREATE INDEX IF NOT EXISTS idx_articles_bias ON articles(bias_label);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(analysis_status);
CREATE INDEX IF NOT EXISTS idx_articles_scraped_at ON articles(scraped_at);

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

    # Write-ahead logging lets page requests read while the pipeline writes.
    # In the default rollback-journal mode any open read blocks a commit (and
    # a pending commit blocks new reads), so concurrent requests and pipeline
    # runs fail with "database is locked". The mode is stored in the database
    # file, so this applies to every later connection.
    mode = cursor.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if mode.lower() != "wal":
        logger.warning(f"Could not enable WAL (journal_mode={mode}); concurrent access may lock")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    cursor.executescript(schema_sql)

    _apply_column_migrations(cursor)
    _backfill_regions(cursor)

    cursor.executescript(_ARTICLE_INDEXES_SQL)

    conn.commit()
    conn.close()
    logger.info("Database initialized")


def _backfill_regions(cursor) -> None:
    """Tag articles and topics stored before regions existed. Back then every
    feed was a U.S. politics or general news feed, so an article whose URL
    names no world section counts as U.S. news, as untagged topics already
    did in the Daily Brief."""
    from backend.pipeline.rss_scraper import US, region_from_url

    rows = cursor.execute("SELECT url FROM articles WHERE region IS NULL AND url IS NOT NULL").fetchall()
    if rows:
        cursor.executemany(
            "UPDATE articles SET region = ? WHERE url = ?",
            [(region_from_url(url) or US, url) for (url,) in rows],
        )
        logger.info(f"Tagged {len(rows)} articles stored before regions existed")
    cursor.execute("UPDATE clusters SET region = ? WHERE region IS NULL", (US,))


def _apply_column_migrations(cursor) -> None:
    """Add columns to existing tables that were defined in earlier schemas.
    Non-destructive — existing rows get NULL / default values.
    """
    article_migrations = [
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
        ("region",                  "TEXT"),
        ("category",                "TEXT"),
    ]
    cluster_migrations = [
        ("detailed_summary",        "TEXT"),
        ("region",                  "TEXT"),
        ("category",                "TEXT"),
        ("outlet_count",            "INTEGER"),
        ("map_json",                "TEXT"),
    ]
    archive_migrations = [
        ("region",                  "TEXT"),
        ("category",                "TEXT"),
        ("policy",                  "INTEGER DEFAULT 0"),
    ]

    for table, migrations in (
        ("articles", article_migrations),
        ("clusters", cluster_migrations),
        ("scraped_articles_archive", archive_migrations),
    ):
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for col, coltype in migrations:
            if col not in existing:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                    logger.info(f"Added column {table}.{col}")
                except sqlite3.OperationalError as e:
                    logger.warning(f"Could not add column {table}.{col}: {e}")

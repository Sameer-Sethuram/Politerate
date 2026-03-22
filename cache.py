"""
cache.py

SQLite-based caching for Politerate pipeline results.
Stores articles, clusters, and metadata for hourly refresh.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

DATABASE_PATH = "politerate.db"
CACHE_MAX_AGE_HOURS = 1


def get_db_path() -> str:
    return DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    logger.info("Initializing database...")
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            source TEXT,
            text TEXT,
            credibility_score REAL DEFAULT 1.0,
            credibility_label TEXT DEFAULT 'unknown',
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cluster_id TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clusters (
            id TEXT PRIMARY KEY,
            summary TEXT,
            highlighted_summary TEXT,
            sources TEXT,
            urls TEXT,
            titles TEXT,
            terms TEXT,
            article_count INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(cluster_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source)
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized")


def save_articles(articles: list[dict]) -> int:
    if not articles:
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    saved = 0

    for article in articles:
        credibility = article.get("credibility", {})
        score = credibility.get("score", 1.0)
        label = credibility.get("bias_label", "unknown")

        cursor.execute("""
            INSERT OR REPLACE INTO articles 
            (url, title, source, text, credibility_score, credibility_label, cluster_id, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            article.get("url", ""),
            article.get("title", ""),
            article.get("source", "unknown"),
            article.get("text", ""),
            score,
            label,
            article.get("cluster_id", ""),
            datetime.now().isoformat()
        ))
        saved += 1

    conn.commit()
    conn.close()
    logger.info(f"Saved {saved} articles to cache")
    return saved


def save_clusters(clusters: list[dict]) -> int:
    if not clusters:
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    saved = 0

    for cluster in clusters:
        cursor.execute("""
            INSERT OR REPLACE INTO clusters
            (id, summary, highlighted_summary, sources, urls, titles, terms, article_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(cluster.get("cluster_id", "")),
            cluster.get("summary", ""),
            cluster.get("highlighted_summary", ""),
            json.dumps(cluster.get("sources", [])),
            json.dumps(cluster.get("urls", [])),
            json.dumps(cluster.get("titles", [])),
            json.dumps(cluster.get("defined_terms", [])),
            cluster.get("article_count", 0),
            datetime.now().isoformat()
        ))

        for article in cluster.get("articles", []):
            cursor.execute("""
                INSERT OR REPLACE INTO articles 
                (url, title, source, text, credibility_score, credibility_label, cluster_id, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.get("url", ""),
                article.get("title", ""),
                article.get("source", "unknown"),
                article.get("text", ""),
                article.get("credibility", {}).get("score", 1.0),
                article.get("credibility", {}).get("bias_label", "unknown"),
                str(cluster.get("cluster_id", "")),
                datetime.now().isoformat()
            ))
        saved += 1

    conn.commit()
    conn.close()
    logger.info(f"Saved {saved} clusters to cache")
    return saved


def update_last_refresh() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value) VALUES ('last_refresh', ?)
    """, (datetime.now().isoformat(),))
    conn.commit()
    conn.close()


def get_last_refresh() -> Optional[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM metadata WHERE key = 'last_refresh'")
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else None


def is_stale() -> bool:
    last_refresh = get_last_refresh()
    if not last_refresh:
        return True

    try:
        last_time = datetime.fromisoformat(last_refresh)
        age_hours = (datetime.now() - last_time).total_seconds() / 3600
        return age_hours >= CACHE_MAX_AGE_HOURS
    except (ValueError, TypeError):
        return True


def get_cached_summaries() -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, summary, highlighted_summary, sources, urls, titles, terms, article_count, updated_at
        FROM clusters
        ORDER BY updated_at DESC
    """)
    rows = cursor.fetchall()

    clusters = []
    for row in rows:
        clusters.append({
            "cluster_id": row["id"],
            "summary": row["summary"],
            "highlighted_summary": row["highlighted_summary"],
            "sources": json.loads(row["sources"]) if row["sources"] else [],
            "urls": json.loads(row["urls"]) if row["urls"] else [],
            "titles": json.loads(row["titles"]) if row["titles"] else [],
            "defined_terms": json.loads(row["terms"]) if row["terms"] else [],
            "article_count": row["article_count"],
            "updated_at": row["updated_at"]
        })

    cursor.execute("SELECT COUNT(*) as count FROM articles")
    article_count = cursor.fetchone()["count"]

    conn.close()

    return {
        "clusters": clusters,
        "article_count": article_count,
        "last_updated": get_last_refresh()
    }


def get_cluster(cluster_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, summary, highlighted_summary, sources, urls, titles, terms, article_count, updated_at
        FROM clusters WHERE id = ?
    """, (cluster_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    cluster = {
        "cluster_id": row["id"],
        "summary": row["summary"],
        "highlighted_summary": row["highlighted_summary"],
        "sources": json.loads(row["sources"]) if row["sources"] else [],
        "urls": json.loads(row["urls"]) if row["urls"] else [],
        "titles": json.loads(row["titles"]) if row["titles"] else [],
        "defined_terms": json.loads(row["terms"]) if row["terms"] else [],
        "article_count": row["article_count"],
        "updated_at": row["updated_at"]
    }

    cursor.execute("""
        SELECT url, title, source, credibility_score, credibility_label
        FROM articles WHERE cluster_id = ?
    """, (cluster_id,))
    articles = []
    for article_row in cursor.fetchall():
        articles.append({
            "url": article_row["url"],
            "title": article_row["title"],
            "source": article_row["source"],
            "credibility_score": article_row["credibility_score"],
            "credibility_label": article_row["credibility_label"]
        })

    conn.close()
    cluster["articles"] = articles
    return cluster


def get_article_count() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM articles")
    count = cursor.fetchone()["count"]
    conn.close()
    return count


def clear_cache() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM articles")
    cursor.execute("DELETE FROM clusters")
    conn.commit()
    conn.close()
    logger.info("Cache cleared")


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DATABASE_PATH}")
    print(f"Last refresh: {get_last_refresh()}")
    print(f"Is stale: {is_stale()}")

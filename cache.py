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
        CREATE TABLE IF NOT EXISTS seen_urls (
            url TEXT PRIMARY KEY,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraped_articles_archive (
            url TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            text TEXT,
            authors TEXT,
            publish_date TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            snapshot_date TEXT PRIMARY KEY,
            snapshot_json TEXT,
            article_count INTEGER,
            cluster_count INTEGER,
            source_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(cluster_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_archive_scraped_at ON scraped_articles_archive(scraped_at)
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

    cursor.execute("DELETE FROM clusters")
    cursor.execute("DELETE FROM articles")

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


def get_all_articles() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT url, title, source, text, cluster_id
        FROM articles
    """)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "url": r["url"],
            "title": r["title"],
            "source": r["source"],
            "text": r["text"],
            "cluster_id": r["cluster_id"],
        }
        for r in rows
    ]


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


def filter_unseen_urls(urls: list[str]) -> list[str]:
    if not urls:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(urls))
    cursor.execute(
        f"SELECT url FROM seen_urls WHERE url IN ({placeholders})",
        urls
    )
    seen = {row["url"] for row in cursor.fetchall()}
    conn.close()
    return [u for u in urls if u not in seen]


def mark_urls_seen(urls: list[str]) -> None:
    if not urls:
        return
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    for url in urls:
        cursor.execute("""
            INSERT INTO seen_urls (url, first_seen, last_seen) VALUES (?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET last_seen = excluded.last_seen
        """, (url, now, now))
    conn.commit()
    conn.close()


def archive_articles(articles: list[dict]) -> int:
    if not articles:
        return 0
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    saved = 0
    for a in articles:
        url = a.get("url", "")
        if not url:
            continue
        authors = a.get("authors") or []
        authors_str = json.dumps(authors) if isinstance(authors, list) else str(authors)
        publish_date = a.get("publish_date")
        publish_date_str = publish_date.isoformat() if hasattr(publish_date, "isoformat") else (publish_date or "")
        cursor.execute("""
            INSERT INTO scraped_articles_archive
            (url, title, source, text, authors, publish_date, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                source = excluded.source,
                text = excluded.text,
                authors = excluded.authors,
                publish_date = excluded.publish_date
        """, (
            url,
            a.get("title", ""),
            a.get("source", "unknown"),
            a.get("text", ""),
            authors_str,
            publish_date_str,
            now
        ))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def get_archived_articles(urls: list[str]) -> dict:
    """Return {url: article_dict} for any URLs present in the archive."""
    if not urls:
        return {}
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(urls))
    cursor.execute(
        f"""SELECT url, title, source, text, authors, publish_date, scraped_at
            FROM scraped_articles_archive WHERE url IN ({placeholders})""",
        urls
    )
    out = {}
    for row in cursor.fetchall():
        try:
            authors = json.loads(row["authors"]) if row["authors"] else []
        except (ValueError, TypeError):
            authors = []
        out[row["url"]] = {
            "url": row["url"],
            "title": row["title"],
            "source": row["source"],
            "text": row["text"],
            "authors": authors,
            "publish_date": row["publish_date"],
            "scraped_at": row["scraped_at"],
        }
    conn.close()
    return out


def prune_archive(days: int = 7) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM scraped_articles_archive
        WHERE scraped_at < datetime('now', ?)
    """, (f"-{days} days",))
    removed = cursor.rowcount
    conn.commit()
    conn.close()
    if removed:
        logger.info(f"Pruned {removed} articles older than {days} days from archive")
    return removed


def save_daily_snapshot(date_str: Optional[str] = None) -> bool:
    """Persist today's cluster state into daily_snapshots. Re-callable (UPSERT)."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    cached = get_cached_summaries()
    clusters = cached.get("clusters", [])

    if not clusters:
        logger.info(f"No clusters to snapshot for {date_str}")
        return False

    all_sources = set()
    total_articles = 0
    for c in clusters:
        all_sources.update(c.get("sources", []))
        total_articles += c.get("article_count", 0)

    snapshot_payload = {
        "date": date_str,
        "clusters": clusters,
        "last_updated": cached.get("last_updated"),
    }

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO daily_snapshots
        (snapshot_date, snapshot_json, article_count, cluster_count, source_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_date) DO UPDATE SET
            snapshot_json = excluded.snapshot_json,
            article_count = excluded.article_count,
            cluster_count = excluded.cluster_count,
            source_count = excluded.source_count,
            created_at = excluded.created_at
    """, (
        date_str,
        json.dumps(snapshot_payload),
        total_articles,
        len(clusters),
        len(all_sources),
        datetime.now().isoformat(),
    ))
    conn.commit()
    conn.close()
    logger.info(f"Saved daily snapshot for {date_str}: {len(clusters)} clusters, {total_articles} articles")
    return True


def get_snapshot(date_str: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT snapshot_date, snapshot_json, article_count, cluster_count, source_count, created_at
        FROM daily_snapshots WHERE snapshot_date = ?
    """, (date_str,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    try:
        payload = json.loads(row["snapshot_json"])
    except (ValueError, TypeError):
        payload = {"clusters": []}
    return {
        "date": row["snapshot_date"],
        "clusters": payload.get("clusters", []),
        "article_count": row["article_count"],
        "cluster_count": row["cluster_count"],
        "source_count": row["source_count"],
        "created_at": row["created_at"],
        "last_updated": payload.get("last_updated"),
    }


def list_snapshot_dates() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT snapshot_date, article_count, cluster_count, source_count, created_at
        FROM daily_snapshots
        ORDER BY snapshot_date DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "date": r["snapshot_date"],
            "article_count": r["article_count"],
            "cluster_count": r["cluster_count"],
            "source_count": r["source_count"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DATABASE_PATH}")
    print(f"Last refresh: {get_last_refresh()}")
    print(f"Is stale: {is_stale()}")

"""
backend/db/cache.py

CRUD helpers for the Politerate SQLite cache — the news pipeline's
working set (articles, clusters, seen URLs, archive, snapshots).

Connection setup + schema lives in `backend/db/connection.py`. Re-exports
`init_db` and `get_connection` here for backward compatibility with
older imports.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional

from backend.config import CACHE_MAX_AGE_HOURS
from backend.db.connection import get_connection, init_db, get_db_path

logger = logging.getLogger(__name__)


def save_articles(articles: list[dict]) -> int:
    if not articles:
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    saved = 0
    now = datetime.now().isoformat()

    for article in articles:
        credibility = article.get("credibility", {})
        analysis = article.get("_analysis") or {}
        article_agg = analysis.get("article") or {}
        has_analysis = bool(analysis)

        cursor.execute("""
            INSERT OR REPLACE INTO articles
            (url, title, source, text, credibility_score, credibility_label, cluster_id, scraped_at,
             analysis_json, article_json, bias_label, dominant_emotion, subjectivity_ratio,
             analysis_status, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            article.get("url", ""),
            article.get("title", ""),
            article.get("source", "unknown"),
            article.get("text", ""),
            credibility.get("score", 1.0),
            credibility.get("bias_label", "unknown"),
            article.get("cluster_id", ""),
            now,
            json.dumps(analysis.get("chunks")) if has_analysis else None,
            json.dumps(article_agg) if has_analysis else None,
            article_agg.get("dominant_bias"),
            article_agg.get("dominant_emotion"),
            article_agg.get("subjectivity_ratio"),
            "done" if has_analysis else "pending",
            now if has_analysis else None,
        ))
        saved += 1

    conn.commit()
    conn.close()
    logger.info(f"Saved {saved} articles to cache")
    return saved


def _cluster_is_good(cluster: dict) -> bool:
    """A cluster is 'good' if it carries a real BART summary — not empty and
    not the [Summary unavailable...] / [No significant news...] placeholder."""
    summary = (cluster.get("summary") or "").strip()
    if not summary:
        return False
    if summary.startswith("["):
        return False
    return True

def save_unclustered_articles(articles: list[dict]) -> int:
    """Persist articles that didn't make it into a named cluster.

    Uses INSERT OR IGNORE so a previously-clustered article is never
    demoted (its cluster_id stays intact if it already exists in the table).
    Each article may carry a 'cluster_id' key set by the caller (e.g.
    'singleton_<hash>' for singletons, or absent for credibility failures).
    """
    if not articles:
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    saved = 0
    now = datetime.now().isoformat()

    for article in articles:
        analysis = article.get("_analysis") or {}
        article_agg = analysis.get("article") or {}
        has_analysis = bool(analysis)
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO articles
                (url, title, source, text, credibility_score, credibility_label, cluster_id, scraped_at,
                 analysis_json, article_json, bias_label, dominant_emotion, subjectivity_ratio,
                 analysis_status, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.get("url", ""),
                article.get("title", ""),
                article.get("source", "unknown"),
                article.get("text", ""),
                article.get("credibility", {}).get("score"),
                article.get("credibility", {}).get("bias_label", "unknown"),
                article.get("cluster_id"),
                now,
                json.dumps(analysis.get("chunks")) if has_analysis else None,
                json.dumps(article_agg) if has_analysis else None,
                article_agg.get("dominant_bias"),
                article_agg.get("dominant_emotion"),
                article_agg.get("subjectivity_ratio"),
                "done" if has_analysis else "pending",
                now if has_analysis else None,
            ))
            saved += 1
        except Exception as e:
            logger.warning(f"Failed to save unclustered article {article.get('url')}: {e}")

    conn.commit()
    conn.close()
    logger.info(f"Saved {saved} unclustered articles")
    return saved


def save_clusters(clusters: list[dict]) -> int:
    """Persist clusters, with a guard against destroying good data.

    If the incoming batch has NO clusters with real summaries (all placeholder
    or empty), we skip the write entirely — the pipeline raced the model
    load or otherwise produced garbage, and the old cached data is better
    than an empty page.

    Stale-while-revalidate contract: callers hit this with every pipeline
    run; we only overwrite when the run actually produced usable output.
    """
    if not clusters:
        return 0

    good_count = sum(1 for c in clusters if _cluster_is_good(c))
    if good_count == 0:
        logger.warning(
            f"save_clusters: {len(clusters)} incoming clusters are all "
            f"placeholder/empty — skipping write to preserve existing cache"
        )
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    saved = 0

    cursor.execute("DELETE FROM clusters")

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
            analysis = article.get("_analysis") or {}
            article_agg = analysis.get("article") or {}
            has_analysis = bool(analysis)
            cursor.execute("""
                INSERT OR REPLACE INTO articles
                (url, title, source, text, credibility_score, credibility_label, cluster_id, scraped_at,
                 analysis_json, article_json, bias_label, dominant_emotion, subjectivity_ratio,
                 analysis_status, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.get("url", ""),
                article.get("title", ""),
                article.get("source", "unknown"),
                article.get("text", ""),
                article.get("credibility", {}).get("score", 1.0),
                article.get("credibility", {}).get("bias_label", "unknown"),
                str(cluster.get("cluster_id", "")),
                datetime.now().isoformat(),
                json.dumps(analysis.get("chunks")) if has_analysis else None,
                json.dumps(article_agg) if has_analysis else None,
                article_agg.get("dominant_bias"),
                article_agg.get("dominant_emotion"),
                article_agg.get("subjectivity_ratio"),
                "done" if has_analysis else "pending",
                datetime.now().isoformat() if has_analysis else None,
            ))
        saved += 1

    conn.commit()
    conn.close()
    logger.info(f"Saved {saved} clusters to cache (good={good_count}/{len(clusters)})")

    # Auto-snapshot the freshly-saved state so there's always a last-known-good
    # snapshot available for stale-while-revalidate fallback. Any save that
    # got past the good_count guard is, by definition, good enough to freeze.
    try:
        save_daily_snapshot()
    except Exception as e:
        logger.warning(f"Post-save snapshot failed (non-fatal): {e}")

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
    """Return the current cluster snapshot. If the live `clusters` table is
    empty OR every cluster is a placeholder (happens when the pipeline
    races the model load), fall back to the most recent daily_snapshot —
    stale data beats an empty page."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, summary, highlighted_summary, sources, urls, titles, terms, article_count, updated_at
        FROM clusters
        ORDER BY article_count DESC, updated_at DESC
    """)
    rows = cursor.fetchall()

    cursor.execute("SELECT url, credibility_score, credibility_label FROM articles")
    cred_by_url = {
        r["url"]: {"score": r["credibility_score"], "label": r["credibility_label"]}
        for r in cursor.fetchall()
    }

    clusters = []
    for row in rows:
        urls = json.loads(row["urls"]) if row["urls"] else []
        source_credibility = [cred_by_url.get(u, {"score": None, "label": "unknown"}) for u in urls]
        clusters.append({
            "cluster_id": row["id"],
            "summary": row["summary"],
            "highlighted_summary": row["highlighted_summary"],
            "sources": json.loads(row["sources"]) if row["sources"] else [],
            "urls": urls,
            "titles": json.loads(row["titles"]) if row["titles"] else [],
            "defined_terms": json.loads(row["terms"]) if row["terms"] else [],
            "source_credibility": source_credibility,
            "article_count": row["article_count"],
            "updated_at": row["updated_at"]
        })

    cursor.execute("SELECT COUNT(*) as count FROM articles")
    article_count = cursor.fetchone()["count"]

    conn.close()

    has_good = any(_cluster_is_good(c) for c in clusters)
    if not has_good:
        fallback = _fallback_to_latest_snapshot()
        if fallback is not None:
            logger.info(
                "get_cached_summaries: live clusters are empty/placeholder — "
                "serving latest daily snapshot instead"
            )
            return fallback

    return {
        "clusters": clusters,
        "article_count": article_count,
        "last_updated": get_last_refresh(),
        "served_from": "live",
    }


def _fallback_to_latest_snapshot() -> Optional[dict]:
    """Return the newest daily_snapshot's cluster payload, or None if there
    are no snapshots yet. Output matches get_cached_summaries()'s shape."""
    snapshots = list_snapshot_dates()
    if not snapshots:
        return None
    newest = snapshots[0]["date"]
    snap = get_snapshot(newest)
    if not snap or not snap.get("clusters"):
        return None
    return {
        "clusters": snap["clusters"],
        "article_count": snap.get("article_count", 0),
        "last_updated": snap.get("last_updated") or snap.get("created_at"),
        "served_from": f"snapshot:{newest}",
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
        SELECT url, title, source, text, credibility_score, credibility_label, bias_label
        FROM articles WHERE cluster_id = ?
    """, (cluster_id,))
    articles = []
    for article_row in cursor.fetchall():
        lean = next(
            (v for v in (article_row["credibility_label"], article_row["bias_label"])
             if v and v != "unknown"),
            None
        )
        articles.append({
            "url": article_row["url"],
            "title": article_row["title"],
            "source": article_row["source"],
            "text": article_row["text"],
            "credibility_score": article_row["credibility_score"],
            "credibility_label": article_row["credibility_label"],
            "lean": lean,
        })

    conn.close()
    cluster["articles"] = articles
    return cluster


def get_all_articles() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT url, title, source, text, cluster_id,
               credibility_score, credibility_label, bias_label,
               dominant_emotion, subjectivity_ratio,
               analysis_status, analysis_json, scraped_at
        FROM articles
        WHERE url IS NOT NULL AND url != ''
        ORDER BY scraped_at DESC
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
            "credibility_score": r["credibility_score"],
            "credibility_label": r["credibility_label"],
            "bias_label": r["bias_label"],
            "dominant_emotion": r["dominant_emotion"],
            "subjectivity_ratio": r["subjectivity_ratio"],
            "analysis_status": r["analysis_status"],
            "in_summary": bool(r["cluster_id"]) and not str(r["cluster_id"]).startswith("singleton_"),
            "scraped_at": r["scraped_at"],
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
    print(f"Database initialized at {get_db_path()}")
    print(f"Last refresh: {get_last_refresh()}")
    print(f"Is stale: {is_stale()}")

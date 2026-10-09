"""
scripts/backfill_analysis.py

Runs DeBERTa on every article in the DB whose `analysis_status='pending'`.
The pipeline only analyzes articles it scrapes fresh — articles already in
`seen_urls` get skipped on subsequent runs and stay pending forever. This
script catches them up so the cluster detail page shows analysis for every
article instead of "Analysis pending" for half of them.

Usage (from project root):
    python -m scripts.backfill_analysis

Idempotent — re-running only touches articles that are still pending.
"""

import json
import logging
import sys
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger("backfill")

from backend.db.connection import get_connection
from backend.inference import get_analyzer


MIN_TEXT_LEN = 100  # Skip articles too short to analyze meaningfully


def fetch_pending_articles(limit: int | None = None) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    sql = """
        SELECT id, url, title, source, text
        FROM articles
        WHERE (analysis_status IS NULL OR analysis_status = 'pending')
          AND text IS NOT NULL
          AND length(text) >= ?
        ORDER BY scraped_at DESC
    """
    params: list = [MIN_TEXT_LEN]
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    cur.execute(sql, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def write_analysis(article_id: int, full_result: dict) -> None:
    """Persist analyzer output back to the article row."""
    chunks = full_result.get("chunks") or []
    article_agg = full_result.get("article") or {}
    now = datetime.now().isoformat()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE articles
        SET analysis_json = ?,
            article_json = ?,
            bias_label = ?,
            dominant_emotion = ?,
            subjectivity_ratio = ?,
            analysis_model_version = ?,
            analysis_status = 'done',
            analyzed_at = ?
        WHERE id = ?
        """,
        (
            json.dumps(chunks),
            json.dumps(article_agg),
            article_agg.get("dominant_bias"),
            article_agg.get("dominant_emotion"),
            article_agg.get("subjectivity_ratio"),
            "deberta-multihead",
            now,
            article_id,
        ),
    )
    conn.commit()
    conn.close()


def main(limit: int | None = None) -> int:
    pending = fetch_pending_articles(limit=limit)
    if not pending:
        logger.info("No pending articles to backfill — everything is already analyzed.")
        return 0

    logger.info(f"Loading analyzer (this may take a minute on first run)...")
    analyzer = get_analyzer()
    version = getattr(analyzer, "model_version", "unknown")
    logger.info(f"Analyzer ready: {type(analyzer).__name__} ({version})")

    logger.info(f"Backfilling analysis for {len(pending)} pending article(s)...")
    t_start = time.time()
    succeeded = 0
    failed = 0
    for i, article in enumerate(pending, 1):
        url = article.get("url", "<no url>")
        try:
            result = analyzer.predict_article(article["text"])
            write_analysis(article["id"], result)
            succeeded += 1
            elapsed = time.time() - t_start
            avg = elapsed / i
            remaining = avg * (len(pending) - i)
            logger.info(
                f"  [{i}/{len(pending)}] OK {url[:80]}  "
                f"(avg {avg:.1f}s/article, ~{remaining/60:.1f}min remaining)"
            )
        except Exception as e:
            failed += 1
            logger.warning(f"  [{i}/{len(pending)}] FAIL {url[:80]}: {type(e).__name__}: {str(e)[:80]}")

    elapsed = time.time() - t_start
    logger.info(
        f"Backfill complete in {elapsed/60:.1f}min: "
        f"{succeeded} succeeded, {failed} failed"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            logger.info(f"Limiting to first {limit} article(s)")
        except ValueError:
            logger.error(f"Invalid limit argument: {sys.argv[1]!r}")
            sys.exit(2)
    sys.exit(main(limit=limit))

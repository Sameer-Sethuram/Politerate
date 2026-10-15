"""
scripts/backfill_summaries.py

Rebuilds topic summaries for clusters saved before per-article
summarization existed, so the Archive and topic pages show the expanded
summaries (multi-outlet brief, overview, attributed details) for past days
too. The pipeline does this for new clusters on every run; this script
catches up the stored ones.

For today's live clusters and every daily snapshot, each cluster's articles
are read back from the articles table, summarized one at a time (stored in
articles.summary, so re-runs only pay for articles not yet summarized), and
the cluster's summary / highlighted_summary / detailed_summary /
defined_terms are rebuilt.

Usage (from project root, with BART available):
    python -m scripts.backfill_summaries                # everything not yet backfilled
    python -m scripts.backfill_summaries 2026-10-01     # one archived day
    python -m scripts.backfill_summaries --force        # rebuild even backfilled clusters

Idempotent — without --force, clusters that already have a detailed summary
are skipped. Summaries are saved as they're generated, so it's safe to stop
and re-run.

Memory: this process loads its own copy of BART (and the embedding model).
On a small server, stop the web service first (`sudo systemctl stop
politerate`) and start it again afterwards; two BART copies at once can
exhaust RAM and stall the site.
"""

import json
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger("backfill_summaries")

from backend.config import BART_MODEL_PATH
from backend.db.cache import get_snapshot, list_snapshot_dates
from backend.db.connection import get_connection, init_db
from backend.pipeline.preprocessor import truncate_to_length
from backend.pipeline.summarizer import PoliteratePipeline

# The pipeline only clusters articles with real text; mirror its minimum.
MIN_ARTICLES = 2


def load_articles(urls: list[str]) -> list[dict]:
    """Article dicts in the shape the pipeline passes to summarize_topic,
    in the cluster's URL order."""
    if not urls:
        return []
    conn = get_connection()
    cur = conn.cursor()
    placeholders = ",".join("?" * len(urls))
    cur.execute(
        f"""SELECT url, title, source, text, credibility_score, summary, summarized_at
            FROM articles WHERE url IN ({placeholders})""",
        urls,
    )
    by_url = {row["url"]: row for row in cur.fetchall()}
    conn.close()

    articles = []
    for url in urls:
        row = by_url.get(url)
        if not row or not row["text"]:
            continue
        articles.append({
            "url": row["url"],
            "title": row["title"],
            "source": row["source"],
            # The stored text is the whole article; summaries are made from
            # the same cut the pipeline summarizes (preprocessor.MAX_TOKENS),
            # whose length also sets BART's output budget.
            "text": truncate_to_length(row["text"]),
            "credibility": {"score": row["credibility_score"]},
            "summary": row["summary"],
            "summarized_at": row["summarized_at"],
        })
    return articles


def rebuild_cluster(pipeline: PoliteratePipeline, urls: list[str]) -> dict | None:
    """Fresh summary fields for a cluster, or None if too few of its
    articles are still stored. New article summaries are saved by the
    pipeline as they're generated."""
    articles = load_articles(urls)
    if len(articles) < MIN_ARTICLES:
        return None
    had_summary = {a["url"] for a in articles if a.get("summary")}
    result = pipeline.build_cluster_summaries(articles)
    new = sum(1 for a in articles if a.get("summary") and a["url"] not in had_summary)
    if new:
        logger.info(f"    summarized {new} new article(s)")
    if not result["summary"] or result["summary"].startswith("["):
        return None
    return result


def backfill_live(pipeline: PoliteratePipeline, force: bool) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, urls, detailed_summary FROM clusters")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    updated = 0
    for row in rows:
        if row["detailed_summary"] and not force:
            continue
        logger.info(f"  live cluster {row['id']}")
        result = rebuild_cluster(pipeline, json.loads(row["urls"] or "[]"))
        if not result:
            logger.info("    skipped (articles no longer stored)")
            continue
        conn = get_connection()
        conn.execute(
            """UPDATE clusters
               SET summary = ?, highlighted_summary = ?, detailed_summary = ?, terms = ?
               WHERE id = ?""",
            (
                result["summary"],
                result["highlighted_summary"],
                json.dumps(result["detailed_summary"]) if result["detailed_summary"] else None,
                json.dumps(result["defined_terms"]),
                row["id"],
            ),
        )
        conn.commit()
        conn.close()
        updated += 1
    return updated


def backfill_snapshot(pipeline: PoliteratePipeline, date: str, force: bool) -> int:
    snap = get_snapshot(date)
    if not snap:
        logger.warning(f"No snapshot for {date}")
        return 0

    conn = get_connection()
    row = conn.execute(
        "SELECT snapshot_json FROM daily_snapshots WHERE snapshot_date = ?", (date,)
    ).fetchone()
    conn.close()
    payload = json.loads(row["snapshot_json"])

    updated = 0
    for cluster in payload.get("clusters", []):
        if cluster.get("detailed_summary") and not force:
            continue
        logger.info(f"  {date} cluster {cluster.get('cluster_id')}")
        result = rebuild_cluster(pipeline, cluster.get("urls") or [])
        if not result:
            logger.info("    skipped (articles no longer stored)")
            continue
        cluster.update(result)
        updated += 1

    if updated:
        conn = get_connection()
        conn.execute(
            "UPDATE daily_snapshots SET snapshot_json = ? WHERE snapshot_date = ?",
            (json.dumps(payload), date),
        )
        conn.commit()
        conn.close()
    return updated


def main(args: list[str]) -> int:
    force = "--force" in args
    dates = [a for a in args if not a.startswith("--")]

    init_db()  # applies the detailed_summary column migration
    pipeline = PoliteratePipeline(model_path=BART_MODEL_PATH)
    pipeline.load_model()
    if not pipeline._model:
        logger.error("BART model failed to load — nothing to backfill with.")
        return 1
    try:
        from backend.pipeline.clustering import ArticleClusterer
        # Its embedding model lets the sentence ranking catch paraphrases.
        pipeline.clusterer = ArticleClusterer()
    except Exception as e:
        logger.warning(f"Embedding model unavailable, using bag-of-words similarity: {e}")

    t_start = time.time()
    total = 0
    if not dates:
        logger.info("Live clusters:")
        total += backfill_live(pipeline, force)
        dates = [s["date"] for s in list_snapshot_dates()]
    for date in dates:
        logger.info(f"Snapshot {date}:")
        total += backfill_snapshot(pipeline, date, force)

    logger.info(f"Backfill complete in {(time.time() - t_start) / 60:.1f}min: {total} cluster(s) rebuilt")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

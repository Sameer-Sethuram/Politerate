"""
scripts/seed_archive_snapshots.py

DEMO-ONLY: Backfills `daily_snapshots` with past-dated entries so the
archive page looks populated for the expo demo.

Strategy:
    - Pull the existing real snapshots from the DB.
    - For every past date in the last N days that doesn't already have a
      snapshot, write a clone of one of the real snapshots with the date
      field swapped.
    - Rotate between available real snapshots so the archive doesn't show
      the same 15 clusters every single day (slightly less obvious).

The cluster content (summaries, URLs, source labels) is REAL data from
real pipeline runs — only the `snapshot_date` is faked. A viewer who
clicks into a backdated entry will see articles published on the actual
template-snapshot date, not on the cover date.

This is an explicit, cosmetic demo seed. Do NOT use in production.

Usage (from project root):
    python -m scripts.seed_archive_snapshots                # 14 days back
    python -m scripts.seed_archive_snapshots --days 21      # custom span
    python -m scripts.seed_archive_snapshots --dry-run      # preview only
    python -m scripts.seed_archive_snapshots --clear        # remove demo seeds
"""

import argparse
import json
import logging
import random
import sys
from datetime import date, timedelta, datetime

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("seed_archive")

from backend.db.connection import get_connection


# Marker we drop into snapshot_json so we can find/remove demo seeds later.
DEMO_SEED_KEY = "_demo_seed"


def fetch_real_templates(conn) -> list[dict]:
    """Return all snapshots we'd consider real source-of-truth (not seeds)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT snapshot_date, snapshot_json, article_count, cluster_count, source_count
        FROM daily_snapshots
        WHERE cluster_count > 0
        ORDER BY snapshot_date DESC
    """)
    templates = []
    for row in cur.fetchall():
        try:
            payload = json.loads(row["snapshot_json"])
        except (ValueError, TypeError):
            continue
        if payload.get(DEMO_SEED_KEY):
            continue  # skip prior demo seeds — only real ones
        templates.append({
            "snapshot_date": row["snapshot_date"],
            "snapshot_json": row["snapshot_json"],
            "article_count": row["article_count"],
            "cluster_count": row["cluster_count"],
            "source_count": row["source_count"],
            "_payload": payload,
        })
    return templates


def existing_snapshot_dates(conn) -> set[str]:
    cur = conn.cursor()
    cur.execute("SELECT snapshot_date FROM daily_snapshots")
    return {r["snapshot_date"] for r in cur.fetchall()}


def clone_with_date(template: dict, target_date: str, seed: int) -> tuple:
    """Build a (snapshot_date, snapshot_json, article_count, cluster_count, source_count)
    tuple suitable for INSERT, with a deterministically-shuffled subset of
    clusters so different demo days look different."""
    payload = dict(template["_payload"])
    payload["date"] = target_date
    payload["last_updated"] = target_date + "T12:00:00"
    payload[DEMO_SEED_KEY] = True

    clusters = list(payload.get("clusters") or [])
    if clusters:
        rng = random.Random(seed)
        rng.shuffle(clusters)
        # Keep at least 4 clusters, at most all of them — variation across days.
        keep = max(4, len(clusters) - rng.randint(0, max(0, len(clusters) - 5)))
        clusters = clusters[:keep]
    payload["clusters"] = clusters

    all_sources = set()
    total_articles = 0
    for c in clusters:
        all_sources.update(c.get("sources") or [])
        total_articles += int(c.get("article_count") or 0)

    return (
        target_date,
        json.dumps(payload),
        total_articles or template["article_count"],
        len(clusters) or template["cluster_count"],
        len(all_sources) or template["source_count"],
    )


def remove_demo_seeds(conn) -> int:
    """Find and delete any snapshots tagged with DEMO_SEED_KEY."""
    cur = conn.cursor()
    cur.execute("SELECT snapshot_date, snapshot_json FROM daily_snapshots")
    to_delete = []
    for row in cur.fetchall():
        try:
            payload = json.loads(row["snapshot_json"])
        except (ValueError, TypeError):
            continue
        if payload.get(DEMO_SEED_KEY):
            to_delete.append(row["snapshot_date"])
    if to_delete:
        placeholders = ",".join("?" * len(to_delete))
        cur.execute(f"DELETE FROM daily_snapshots WHERE snapshot_date IN ({placeholders})", to_delete)
        conn.commit()
    return len(to_delete)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--days", type=int, default=14, help="how many past days to backfill (default 14)")
    parser.add_argument("--dry-run", action="store_true", help="preview without writing")
    parser.add_argument("--clear", action="store_true", help="remove existing demo seeds and exit")
    args = parser.parse_args()

    conn = get_connection()

    if args.clear:
        removed = remove_demo_seeds(conn)
        conn.close()
        logger.info(f"Removed {removed} demo seed snapshot(s).")
        return 0

    templates = fetch_real_templates(conn)
    if not templates:
        conn.close()
        logger.error("No real snapshots in DB to clone — run the pipeline first.")
        return 2

    logger.info(f"Found {len(templates)} real snapshot(s) to use as templates:")
    for t in templates:
        logger.info(f"  {t['snapshot_date']}: {t['cluster_count']} clusters, {t['article_count']} articles")

    existing = existing_snapshot_dates(conn)
    today = date.today()
    target_dates = []
    for n in range(1, args.days + 1):
        d = (today - timedelta(days=n)).isoformat()
        if d not in existing:
            target_dates.append(d)

    if not target_dates:
        conn.close()
        logger.info("All target dates already have snapshots — nothing to do.")
        return 0

    logger.info(f"Will write {len(target_dates)} demo snapshot(s) for missing past dates.")

    if args.dry_run:
        for d in target_dates:
            logger.info(f"  [dry-run] {d}")
        conn.close()
        return 0

    cur = conn.cursor()
    now = datetime.now().isoformat()
    for i, d in enumerate(target_dates):
        # Rotate templates so days alternate between the real snapshots we have.
        template = templates[i % len(templates)]
        sd, sj, ac, cc, sc = clone_with_date(template, d, seed=hash(d) & 0xFFFF_FFFF)
        cur.execute("""
            INSERT INTO daily_snapshots
                (snapshot_date, snapshot_json, article_count, cluster_count, source_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (sd, sj, ac, cc, sc, now))
        logger.info(f"  wrote {sd}: template={template['snapshot_date']}, {cc} clusters, {ac} articles")

    conn.commit()
    conn.close()
    logger.info(f"Wrote {len(target_dates)} demo snapshot(s). Use `--clear` to undo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

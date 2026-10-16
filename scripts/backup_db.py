"""
scripts/backup_db.py

Saves a copy of the SQLite database and deletes copies older than a week,
so there is always a week of backups to restore from.

Uses SQLite's backup API, which makes a consistent copy even while the web
service is reading and writing. Copying politerate.db with `cp` isn't safe:
in WAL mode the latest changes may still be in politerate.db-wal. Each
backup is checked for corruption, then saved as one self-contained file:

    ~/politerate_backups/politerate-2026-10-13_033000.db

After a successful backup, copies older than KEEP_DAYS are deleted, but
the KEEP_MIN newest are always kept. A failed backup deletes nothing.

Usage (from project root):
    python -m scripts.backup_db                          # nightly (cron)
    python -m scripts.backup_db --label before-deploy    # before risky changes
    python -m scripts.backup_db --dir /mnt/backups       # somewhere else
    python -m scripts.backup_db --verify                 # test-restore the newest backup
    python -m scripts.backup_db --verify path/to/x.db    # test-restore that one

The backup folder defaults to ~/politerate_backups (POLITERATE_BACKUP_DIR
overrides it). Run it as the user that owns politerate.db.

--verify restores a backup into a scratch folder the way the steps below
do, starts the site's database code on the copy (init_db, then the reads
behind the Daily Brief and the Archive) and prints what it found. It never
touches politerate.db or the service. Exits 1 if the backup is unusable.

Restore: stop the service, move politerate.db (and any politerate.db-wal /
politerate.db-shm next to it) out of the way, copy a backup to
politerate.db, start the service.
"""

import argparse
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from backend.config import BACKUP_DIR, DB_PATH, PROJECT_ROOT, site_now
from backend.db.connection import BUSY_TIMEOUT_SECONDS

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backup_db")

# Backups older than this are deleted after each successful backup...
KEEP_DAYS = 7
# ...except the newest KEEP_MIN, which are always kept: after the server has
# been down for over a week, its first backup back must not delete every
# older copy.
KEEP_MIN = 7
# Disk space that must remain free after the backup is written. The live
# database writes to the same disk, and a full disk would break the site.
MIN_FREE_AFTER_BACKUP_BYTES = 1024 ** 3
# An unfinished copy older than this was left by a backup that was killed.
STALE_PARTIAL_SECONDS = 3600

_TIME_FORMAT = "%Y-%m-%d_%H%M%S"
_BACKUP_NAME = re.compile(r"^politerate-(\d{4}-\d{2}-\d{2}_\d{6})(?:-[\w-]+)?\.db$")
_LABEL = re.compile(r"[\w-]*")


def backup_time(path: Path):
    """When a backup was taken, from its file name; None for other files."""
    match = _BACKUP_NAME.match(path.name)
    return datetime.strptime(match.group(1), _TIME_FORMAT) if match else None


def backup(db_path: Path, backup_dir: Path, label: str = "") -> Path:
    """Copy the database into backup_dir and return the new file's path.
    The copy is written under a temporary name and renamed only once it has
    passed an integrity check, so a backup file is never half-written."""
    if not db_path.exists():
        raise FileNotFoundError(f"no database at {db_path}")
    backup_dir.mkdir(parents=True, exist_ok=True)

    for partial in backup_dir.glob("politerate-*.db.partial"):
        if time.time() - partial.stat().st_mtime > STALE_PARTIAL_SECONDS:
            partial.unlink()
            logger.info(f"Deleted unfinished copy {partial.name}")

    wal_path = db_path.with_name(db_path.name + "-wal")
    needed = db_path.stat().st_size + (wal_path.stat().st_size if wal_path.exists() else 0)
    free = shutil.disk_usage(backup_dir).free
    if free - needed < MIN_FREE_AFTER_BACKUP_BYTES:
        raise RuntimeError(
            f"not enough disk space: the backup needs {needed / 1024**2:.0f} MB and "
            f"{free / 1024**2:.0f} MB is free, but at least "
            f"{MIN_FREE_AFTER_BACKUP_BYTES / 1024**2:.0f} MB must stay free"
        )

    name = f"politerate-{site_now().strftime(_TIME_FORMAT)}{'-' + label if label else ''}.db"
    final = backup_dir / name
    partial = backup_dir / (name + ".partial")
    try:
        source = sqlite3.connect(str(db_path), timeout=BUSY_TIMEOUT_SECONDS)
        copy = sqlite3.connect(str(partial))
        try:
            source.backup(copy)
            # Store the copy in the default rollback-journal mode, so opening
            # it (to inspect or test a restore) doesn't create -wal / -shm
            # files in the backup folder. init_db switches a restored copy
            # back to WAL.
            copy.execute("PRAGMA journal_mode=DELETE")
            check = copy.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            copy.close()
            source.close()
        if check != "ok":
            raise RuntimeError(f"the copy failed its integrity check: {check}")
        os.replace(partial, final)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return final


def rotate(backup_dir: Path, now: datetime) -> list[Path]:
    """Delete backups older than KEEP_DAYS, keeping at least the KEEP_MIN
    newest. Only files named like backups are touched. Returns the deleted
    paths."""
    backups = sorted(
        ((taken, path) for path in backup_dir.iterdir() if (taken := backup_time(path))),
        reverse=True,
    )
    cutoff = now - timedelta(days=KEEP_DAYS)
    deleted = []
    for taken, path in backups[KEEP_MIN:]:
        if taken < cutoff:
            path.unlink()
            deleted.append(path)
    return deleted


REQUIRED_TABLES = ("articles", "clusters", "metadata", "seen_urls", "scraped_articles_archive", "daily_snapshots")

# Run in a separate Python process with POLITERATE_DB_PATH pointing at the
# restored copy, so the app's own database code opens it exactly as the
# service would after a restore (WAL mode, column migrations, indexes).
_RESTORED_APP_CHECK = """
import json
from backend.db.connection import init_db
from backend.db import cache
init_db()
dates = cache.list_snapshot_dates()
newest = cache.get_archive_day(dates[0]["date"]) if dates else None
print(json.dumps({
    "today_topics": len(cache.get_cached_summaries()["clusters"]),
    "archive_days": len(dates),
    "newest_archive_day": dates[0]["date"] if dates else None,
    "newest_archive_topics": len(newest["clusters"]) if newest else 0,
    "last_refresh": cache.get_last_refresh(),
}))
"""


def newest_backup(backup_dir: Path):
    backups = sorted((taken, path) for path in backup_dir.glob("politerate-*.db") if (taken := backup_time(path)))
    return backups[-1][1] if backups else None


def verify(backup_path: Path) -> bool:
    """Test-restore `backup_path` into a scratch folder next to it and check
    the copy is complete and the site can open it. Logs what it finds;
    True if the backup is usable."""
    if not backup_path.is_file():
        logger.error(f"No backup at {backup_path}")
        return False
    # Next to the backups, whose disk backup() keeps space free on.
    with tempfile.TemporaryDirectory(dir=backup_path.parent, prefix=".restore-test-") as scratch:
        restored = Path(scratch) / "politerate.db"
        shutil.copy2(backup_path, restored)

        conn = sqlite3.connect(str(restored))
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in REQUIRED_TABLES if t in tables}
        finally:
            conn.close()

        problems = []
        if integrity != "ok":
            problems.append(f"integrity check failed: {integrity}")
        missing = [t for t in REQUIRED_TABLES if t not in tables]
        if missing:
            problems.append(f"missing tables: {', '.join(missing)}")
        if counts.get("articles", 0) == 0:
            problems.append("no articles")

        app_check = None
        if not problems:
            result = subprocess.run(
                [sys.executable, "-c", _RESTORED_APP_CHECK],
                cwd=PROJECT_ROOT, env={**os.environ, "POLITERATE_DB_PATH": str(restored)},
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                problems.append(f"the site's database code failed on the restored copy:\n{result.stderr.strip()[-2000:]}")
            else:
                app_check = json.loads(result.stdout.strip().splitlines()[-1])

    logger.info(f"Restore test of {backup_path.name} ({backup_path.stat().st_size / 1024**2:.1f} MB)")
    logger.info("  rows: " + ", ".join(f"{t} {n:,}" for t, n in counts.items()))
    if app_check:
        logger.info(
            f"  the site opened it: {app_check['archive_days']} archived days (newest "
            f"{app_check['newest_archive_day']}, {app_check['newest_archive_topics']} topics), "
            f"last pipeline run {app_check['last_refresh']}, {app_check['today_topics']} topics dated today"
        )
    for problem in problems:
        logger.error(f"  {problem}")
    if problems:
        logger.error("Restore test FAILED: don't rely on this backup")
        return False
    logger.info("Restore test passed: this backup can be restored")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Back up the Politerate database and delete old backups.")
    parser.add_argument("--dir", type=Path, default=BACKUP_DIR,
                        help=f"backup folder (default: {BACKUP_DIR})")
    parser.add_argument("--label", default="",
                        help="added to the file name, e.g. before-deploy (letters, digits, - and _)")
    parser.add_argument("--verify", nargs="?", const="newest", metavar="BACKUP",
                        help="test-restore a backup instead of making one (default: the newest in --dir)")
    args = parser.parse_args(argv)
    if not _LABEL.fullmatch(args.label):
        parser.error("--label may only contain letters, digits, - and _")

    if args.verify:
        path = newest_backup(args.dir) if args.verify == "newest" else Path(args.verify)
        if path is None:
            logger.error(f"No backups in {args.dir} to test")
            return 1
        return 0 if verify(path) else 1

    started = time.time()
    try:
        path = backup(DB_PATH, args.dir, args.label)
    except Exception as e:
        logger.error(f"Backup failed, no old backups deleted: {e}")
        return 1
    logger.info(
        f"Backed up {DB_PATH} to {path} "
        f"({path.stat().st_size / 1024**2:.1f} MB, {time.time() - started:.1f}s)"
    )

    for old in rotate(args.dir, site_now()):
        logger.info(f"Deleted old backup {old.name}")
    kept = sorted(p.name for p in args.dir.iterdir() if backup_time(p))
    logger.info(f"{len(kept)} backups in {args.dir}: oldest {kept[0]}, newest {kept[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

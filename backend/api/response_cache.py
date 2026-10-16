"""
backend/api/response_cache.py

Keeps built API responses in memory between pipeline runs. What the read
endpoints serve changes only when the hourly pipeline saves or a snapshot
is taken, yet building some of them means parsing every topic's JSON, a
week of snapshots, or a day of article text, on every page load.

main.py calls clear() after each pipeline run and snapshot. Entries also
expire after TTL_SECONDS, so changes made by another process (a backfill
script) still show up, and every key includes the site's date, so nothing
from yesterday is served after midnight.

Cached values are shared between requests: callers must not modify them.
"""

import threading
import time

from backend.db.cache import today_str

TTL_SECONDS = 10 * 60
# Bounds memory when keys come from the URL (topic IDs, archive dates).
MAX_ENTRIES = 256

_entries: dict = {}
_generation = 0
_lock = threading.Lock()


def cached(key: tuple, build):
    """build()'s result for `key`, reused until clear() or TTL_SECONDS."""
    key = (today_str(), *key)
    now = time.monotonic()
    with _lock:
        entry = _entries.get(key)
        if entry and now - entry[0] < TTL_SECONDS:
            return entry[1]
        generation = _generation

    value = build()

    with _lock:
        # Not stored if clear() ran while building: the value may predate
        # the data that triggered it.
        if generation == _generation:
            if key not in _entries and len(_entries) >= MAX_ENTRIES:
                _entries.pop(next(iter(_entries)))
            _entries[key] = (now, value)
    return value


def clear() -> None:
    global _generation  # noqa: PLW0603
    with _lock:
        _entries.clear()
        _generation += 1

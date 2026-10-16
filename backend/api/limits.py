"""
backend/api/limits.py

Request limits for the API:

  - rate_limit: requests per visitor IP over sliding windows (429 past it)
  - inference_slot: caps how many model runs (DeBERTa, BART) happen at
    once, so a few analyzer requests can't take every gunicorn thread and
    stall page loads (503 while all slots are taken)
  - require_admin: the X-Admin-Token check for endpoints that change data

Counters live in this process's memory. That is correct because
production runs one gunicorn worker (the scheduler needs it); with several
workers each would count on its own and the limits would multiply.
"""

import functools
import hmac
import math
import os
import threading
import time
from collections import deque

from flask import jsonify, request

from backend.config import ADMIN_TOKEN

MINUTE = 60
HOUR = 60 * MINUTE

# Every /api/ request counts toward this, per IP. Generous on purpose:
# a classroom or office shares one public IP, and responses are cached, so
# it only stops one client hammering the site. A load test from a single
# machine needs it raised (POLITERATE_API_RATE_PER_MINUTE).
API_LIMITS = ((int(os.environ.get("POLITERATE_API_RATE_PER_MINUTE", "600")), MINUTE),)

# Model runs at once across all visitors. Each holds a gunicorn thread (of
# 4) for seconds to minutes on CPU; two leaves two for everything else.
INFERENCE_SLOTS = 2


class RateLimiter:
    """Sliding-window counts of requests per (bucket, client)."""

    def __init__(self):
        self._hits: dict[tuple[str, str], deque] = {}
        self._windows: dict[str, int] = {}
        self._last_logged: dict[str, float] = {}
        self._lock = threading.Lock()
        self._next_sweep = 0.0

    def hit(self, bucket: str, client: str, limits) -> float | None:
        """Count one request. Returns None if it's allowed, else the seconds
        until it would be. `limits` is ((max requests, window seconds), ...).
        Refused requests aren't counted, so retrying doesn't extend a wait."""
        now = time.monotonic()
        with self._lock:
            self._windows[bucket] = max(window for _, window in limits)
            self._sweep(now)
            hits = self._hits.get((bucket, client))
            if hits is None:
                hits = self._hits[(bucket, client)] = deque(maxlen=max(count for count, _ in limits))
            for count, window in limits:
                in_window = [t for t in hits if now - t < window]
                if len(in_window) >= count:
                    return window - (now - in_window[-count])
            hits.append(now)
            return None

    def _sweep(self, now: float) -> None:
        """Forget clients idle for longer than their bucket's longest window,
        so the table doesn't grow with every IP that ever visited."""
        if now < self._next_sweep:
            return
        self._next_sweep = now + MINUTE
        for key in [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= self._windows[k[0]]]:
            del self._hits[key]
        for client in [c for c, t in self._last_logged.items() if now - t >= MINUTE]:
            del self._last_logged[client]

    def should_log(self, client: str) -> bool:
        """True at most once a minute per client, so a client hammering the
        site leaves one log line a minute rather than one per request."""
        now = time.monotonic()
        with self._lock:
            if now - self._last_logged.get(client, -MINUTE) < MINUTE:
                return False
            self._last_logged[client] = now
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._last_logged.clear()


limiter = RateLimiter()
_inference_slots = threading.BoundedSemaphore(INFERENCE_SLOTS)


def client_ip() -> str:
    # Already the visitor's IP behind a proxy: main.py applies ProxyFix when
    # POLITERATE_TRUSTED_PROXIES is set.
    return request.remote_addr or "unknown"


def error_response(status: int, message: str, retry_after: float | None = None):
    response = jsonify({"error": message})
    response.status_code = status
    if retry_after is not None:
        response.headers["Retry-After"] = str(max(1, math.ceil(retry_after)))
    return response


def too_many_requests(retry_after: float):
    seconds = max(1, math.ceil(retry_after))
    return error_response(
        429, f"Too many requests. Please wait {seconds} second{'s' if seconds != 1 else ''} and try again.",
        retry_after,
    )


def rate_limit(bucket: str, *limits):
    """Limit a view to `limits` ((max requests, window seconds), ...) per IP,
    on top of the site-wide API_LIMITS."""
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            retry_after = limiter.hit(bucket, client_ip(), limits)
            if retry_after is not None:
                return too_many_requests(retry_after)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def inference_slot(view):
    """Run the view only while holding one of INFERENCE_SLOTS; answer 503
    right away when all are taken rather than queueing, since a queued
    request would hold a gunicorn thread while it waits."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not _inference_slots.acquire(blocking=False):
            return error_response(
                503, "The analyzer is busy with other requests. Please try again in a few seconds.", 10,
            )
        try:
            return view(*args, **kwargs)
        finally:
            _inference_slots.release()
    return wrapped


def require_admin(view):
    """Only with the X-Admin-Token header matching POLITERATE_ADMIN_TOKEN.
    With no token configured the endpoint is off entirely."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not ADMIN_TOKEN:
            return error_response(403, "This endpoint is disabled (POLITERATE_ADMIN_TOKEN is not set).")
        sent = request.headers.get("X-Admin-Token", "")
        if not hmac.compare_digest(sent.encode(), ADMIN_TOKEN.encode()):
            return error_response(403, "A valid X-Admin-Token header is required.")
        return view(*args, **kwargs)
    # Rate limited first, so the token can't be guessed by brute force.
    return rate_limit("admin", (10, MINUTE))(wrapped)

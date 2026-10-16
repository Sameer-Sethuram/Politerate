"""
scripts/load_test.py

Simulates many visitors using the site at once and reports how each API
endpoint held up: response times (median, 95th percentile, slowest),
errors, and requests turned away by the rate limits.

Each simulated visitor opens a random page, makes the API calls that page
makes in the browser, pauses as if reading, and repeats until time is up.
The analyzer (heavy model inference) is left out unless --analyze is given.

Usage (from project root):
    python -m scripts.load_test --url http://localhost:5000 --users 25 --duration 60
    python -m scripts.load_test --url https://your-site --users 10 --analyze

All simulated visitors share this machine's IP, so they share its rate
limits: past a few hundred requests a minute, 429s are the limit working.
Raise POLITERATE_API_RATE_PER_MINUTE on the server under test to measure
capacity instead. Only load a server you're allowed to, and prefer a copy
of the site to production.

Exits 1 if more than --max-error-rate of requests failed (5xx, timeouts,
connection errors; 429s are reported but not counted as failures).
"""

import argparse
import random
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests

ANALYZE_TEXT = (
    "The Senate voted on the filibuster reform bill today, with reconciliation being discussed "
    "as an alternative approach. Supporters said the change was overdue; opponents warned it "
    "would erode minority rights in the chamber for decades to come. "
) * 6


def page_requests(page: str, topic_ids: list[str], archive_dates: list[str]) -> list[tuple[str, str, dict]]:
    """The (method, path, kwargs) calls the frontend makes to show `page`."""
    if page == "home":
        return [("GET", "/api/daily-summary", {})]
    if page == "topics":
        return [("GET", "/api/summaries", {})]
    if page == "all-articles":
        return [("GET", "/api/all-articles", {})]
    if page == "glossary":
        return [("GET", "/api/glossary", {}), ("GET", "/api/glossary/categories", {})]
    if page == "learn":
        return [("GET", "/api/quiz?count=5", {}), ("GET", "/api/term-of-day", {})]
    if page == "archive":
        calls = [("GET", "/api/archive", {})]
        if archive_dates:
            calls.append(("GET", f"/api/archive/{random.choice(archive_dates)}", {}))
        return calls
    if page == "topic" and topic_ids:
        topic = random.choice(topic_ids)
        return [("GET", f"/api/summaries/{topic}", {}), ("GET", f"/api/cluster/{topic}/analysis", {})]
    if page == "analyzer":
        return [("POST", "/api/analyze", {"json": {"text": ANALYZE_TEXT}})]
    return [("GET", "/", {})]


class Results:
    def __init__(self):
        self.lock = threading.Lock()
        self.times = defaultdict(list)
        self.statuses = defaultdict(lambda: defaultdict(int))

    def record(self, endpoint: str, status: str, seconds: float):
        with self.lock:
            self.times[endpoint].append(seconds)
            self.statuses[endpoint][status] += 1


def endpoint_name(path: str) -> str:
    """Groups per-topic and per-date paths under one name."""
    parts = path.split("?")[0].split("/")
    if path.startswith("/api/summaries/"):
        return "/api/summaries/<id>"
    if path.startswith("/api/cluster/"):
        return "/api/cluster/<id>/analysis"
    if path.startswith("/api/archive/") and len(parts) == 4:
        return "/api/archive/<date>"
    return path.split("?")[0]


def visitor(base: str, deadline: float, pages: list[str], think: float, timeout: float,
            topic_ids, archive_dates, results: Results):
    session = requests.Session()
    while time.time() < deadline:
        for method, path, kwargs in page_requests(random.choice(pages), topic_ids, archive_dates):
            started = time.perf_counter()
            try:
                response = session.request(method, base + path, timeout=timeout, **kwargs)
                status = str(response.status_code)
            except requests.Timeout:
                status = "timeout"
            except requests.RequestException:
                status = "conn-error"
            results.record(endpoint_name(path), status, time.perf_counter() - started)
        time.sleep(random.uniform(think / 2, think * 1.5))


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * pct))]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Simulate simultaneous visitors and report API response times.")
    parser.add_argument("--url", default="http://localhost:5000", help="site to test (default: %(default)s)")
    parser.add_argument("--users", type=int, default=25, help="simultaneous visitors (default: %(default)s)")
    parser.add_argument("--duration", type=float, default=60, help="seconds to run (default: %(default)s)")
    parser.add_argument("--think", type=float, default=2.0,
                        help="average seconds a visitor pauses between pages (default: %(default)s)")
    parser.add_argument("--timeout", type=float, default=30, help="seconds before a request counts as timed out")
    parser.add_argument("--analyze", action="store_true", help="also submit text to the analyzer (heavy)")
    parser.add_argument("--max-error-rate", type=float, default=0.01,
                        help="fail if more than this share of requests fail (default: %(default)s)")
    args = parser.parse_args(argv)
    base = args.url.rstrip("/")

    # Real topic IDs and archive dates, so detail pages hit existing data.
    try:
        topic_ids = [str(c["cluster_id"]) for c in requests.get(f"{base}/api/summaries", timeout=60).json()["clusters"]]
        archive_dates = [s["date"] for s in requests.get(f"{base}/api/archive", timeout=60).json()["snapshots"]][:7]
    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"Could not reach {base}: {e}")
        return 1

    pages = ["home", "home", "home", "topics", "topics", "all-articles", "glossary", "learn", "archive", "topic", "topic"]
    if args.analyze:
        pages.append("analyzer")

    print(f"{args.users} visitors for {args.duration:.0f}s against {base} "
          f"({len(topic_ids)} topics, {len(archive_dates)} archive days)...")
    results = Results()
    deadline = time.time() + args.duration
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.users) as pool:
        for _ in range(args.users):
            pool.submit(visitor, base, deadline, pages, args.think, args.timeout, topic_ids, archive_dates, results)
    elapsed = time.time() - started

    total = failed = limited = 0
    print(f"\n{'endpoint':30} {'requests':>8} {'median':>8} {'p95':>8} {'slowest':>8}  statuses")
    for endpoint in sorted(results.times):
        times = results.times[endpoint]
        statuses = results.statuses[endpoint]
        total += len(times)
        failed += sum(n for s, n in statuses.items() if not s.isdigit() or s.startswith("5"))
        limited += statuses.get("429", 0)
        summary = " ".join(f"{s}x{n}" for s, n in sorted(statuses.items()))
        print(f"{endpoint:30} {len(times):8} {percentile(times, .5) * 1000:6.0f}ms {percentile(times, .95) * 1000:6.0f}ms "
              f"{max(times) * 1000:6.0f}ms  {summary}")

    error_rate = failed / total if total else 1.0
    print(f"\n{total} requests in {elapsed:.0f}s ({total / elapsed:.1f}/s), "
          f"{failed} failed ({error_rate:.1%}), {limited} rate-limited (429)")
    if limited:
        print("429s mean the rate limits turned requests away; see the note in this script's docstring.")
    return 1 if error_rate > args.max_error_rate else 0


if __name__ == "__main__":
    sys.exit(main())

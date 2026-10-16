"""
backend/api/main.py

Flask application factory for Politerate. Mirrors Sarah's
`backend/api/main.py` layout: app setup + blueprint registration +
model/scheduler lifecycle in one place.

Run via `python run.py` at the project root.
"""

import gzip
import logging
import threading
import time

from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from backend.api import response_cache
from backend.api.limits import API_LIMITS, client_ip, limiter, too_many_requests
from backend.config import (
    BART_MODEL_PATH,
    CORS_ORIGINS,
    MAX_REQUEST_BYTES,
    STATIC_DIR,
    TEMPLATES_DIR,
    TIMEZONE,
    TRUSTED_PROXIES,
)
from backend.db.cache import is_stale
from backend.db.connection import init_db
# Under systemd this goes to the journal: `journalctl -u politerate -p warning`
# lists warnings and errors, with tracebacks for unhandled ones.
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Requests slower than this are logged as warnings, to spot endpoints that
# struggle under load.
SLOW_REQUEST_SECONDS = 5
# JSON responses smaller than this aren't worth compressing.
GZIP_MIN_BYTES = 1024
# Exempt from the site-wide rate limit: uptime monitors poll it.
_UNLIMITED_PATHS = {"/api/health"}

# ---------------------------------------------------------------------------
# Module-level state (BART summarizer + scheduler). Kept here so blueprints
# can import it; loaded once in initialize().
# ---------------------------------------------------------------------------
_model = None
_tokenizer = None
# On the site's clock, so the 23:55 snapshot runs at 11:55 p.m. Eastern
# rather than the server's 23:55.
scheduler = BackgroundScheduler(timezone=TIMEZONE)
# Held for a whole pipeline run. The hourly job, the startup run and
# /api/refresh would otherwise overlap, and two runs fight over SQLite and
# RAM and save each other's half-finished clusters.
_pipeline_lock = threading.Lock()


def pipeline_running() -> bool:
    return _pipeline_lock.locked()


def create_app() -> Flask:
    """Flask app factory. Pins template/static folders to project root so
    Flask finds them regardless of where this module lives in the tree."""
    app = Flask(
        __name__,
        template_folder=str(TEMPLATES_DIR),
        static_folder=str(STATIC_DIR),
    )
    # Larger bodies get a 413 before any of them is read.
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
    if TRUSTED_PROXIES:
        # Take the visitor's IP from X-Forwarded-For, as set by that many
        # proxies, so rate limits count visitors rather than the proxy.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=TRUSTED_PROXIES, x_proto=TRUSTED_PROXIES)

    @app.before_request
    def _start_request():
        request.started_at = time.monotonic()
        if request.path.startswith("/api/") and request.path not in _UNLIMITED_PATHS:
            retry_after = limiter.hit("api", client_ip(), API_LIMITS)
            if retry_after is not None:
                if limiter.should_log(client_ip()):
                    logger.warning(
                        f"Rate limited {client_ip()} on {request.method} {request.path} "
                        f"(logged once a minute per IP)"
                    )
                return too_many_requests(retry_after)

    # Permissive CORS for the React dev server (and any future origins set
    # via POLITERATE_CORS_ORIGINS). Only fires when Origin header is set,
    # so server-rendered templates are unaffected.
    @app.after_request
    def _apply_cors(response):
        origin = request.headers.get("Origin")
        if origin and (origin in CORS_ORIGINS or "*" in CORS_ORIGINS):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    # The All Articles payload (a week of articles) runs to hundreds of KB
    # of JSON, which compresses about tenfold.
    @app.after_request
    def _compress(response):
        if (
            response.mimetype == "application/json"
            and not response.direct_passthrough
            and "gzip" in request.headers.get("Accept-Encoding", "")
            and "Content-Encoding" not in response.headers
        ):
            body = response.get_data()
            if len(body) >= GZIP_MIN_BYTES:
                response.set_data(gzip.compress(body, compresslevel=6))
                response.headers["Content-Encoding"] = "gzip"
            response.vary.add("Accept-Encoding")
        return response

    @app.after_request
    def _log_slow_request(response):
        started = getattr(request, "started_at", None)
        if started is not None and time.monotonic() - started > SLOW_REQUEST_SECONDS:
            logger.warning(
                f"Slow request: {request.method} {request.full_path.rstrip('?')} took "
                f"{time.monotonic() - started:.1f}s (status {response.status_code})"
            )
        return response

    # API errors come back as JSON {"error": ...}, which the frontend shows;
    # other paths keep Flask's pages.
    @app.errorhandler(HTTPException)
    def _http_error(e):
        if not request.path.startswith("/api/"):
            return e
        message = e.name
        if e.code == 413:
            message = f"Request is too large (limit {MAX_REQUEST_BYTES // 1024} KB)."
        response = jsonify({"error": message})
        response.status_code = e.code
        return response

    @app.errorhandler(Exception)
    def _unhandled_error(e):
        # Flask doesn't log exceptions that a handler takes, so log here,
        # with the traceback. The visitor gets no internals.
        logger.exception(f"Unhandled error on {request.method} {request.full_path.rstrip('?')}")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Something went wrong on our side. Please try again."}), 500
        return "Internal server error", 500

    from backend.api.routes.pages import pages_bp
    from backend.api.routes.articles import articles_bp
    from backend.api.routes.analyze import analyze_bp
    from backend.api.routes.glossary import glossary_bp
    from backend.api.routes.archive import archive_bp
    from backend.api.routes.quiz import quiz_bp
    from backend.api.routes.system import system_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(articles_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(glossary_bp)
    app.register_blueprint(archive_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(system_bp)

    return app


# ---------------------------------------------------------------------------
# BART summarizer loader (used by /api/summarize debug endpoint and the
# scheduled pipeline update).
# ---------------------------------------------------------------------------
def load_model():
    global _model, _tokenizer  # noqa: PLW0603
    try:
        from transformers import BartForConditionalGeneration, BartTokenizer
        import torch

        logger.info(f"Loading summarization model from {BART_MODEL_PATH}...")
        _tokenizer = BartTokenizer.from_pretrained(BART_MODEL_PATH)
        _model = BartForConditionalGeneration.from_pretrained(BART_MODEL_PATH)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = _model.to(device)
        _model.eval()
        logger.info(f"Model loaded on {device}")
    except Exception:
        logger.exception("Failed to load model")

def load_analyzer():
    from backend.inference import get_analyzer
    try:
        analyzer = get_analyzer()
        logger.info("Analyzer ready: %s", type(analyzer).__name__)
    except Exception as e:
        logger.error("Failed to load analyzer: %s", e)
        raise

    
def generate_summary(text: str, max_length: int = 150, min_length: int = 50) -> str:
    if not _model:
        return "[Summary unavailable - model not loaded]"

    inputs = _tokenizer(
        text,
        max_length=1024,
        truncation=True,
        return_tensors="pt"
    ).to(_model.device)

    summary_ids = _model.generate(
        inputs["input_ids"],
        num_beams=4,
        max_length=max_length,
        min_length=min_length,
        early_stopping=True
    )

    return _tokenizer.decode(summary_ids[0], skip_special_tokens=True)


# ---------------------------------------------------------------------------
# Scheduled pipeline jobs
# ---------------------------------------------------------------------------
def run_pipeline_update() -> bool:
    """One pipeline run, unless one is already going (then False at once)."""
    if not _pipeline_lock.acquire(blocking=False):
        logger.warning("Pipeline update already running, not starting another")
        return False
    try:
        return _run_pipeline_update()
    finally:
        _pipeline_lock.release()
        # Pages show the new topics from the next request on.
        response_cache.clear()


def _run_pipeline_update() -> bool:
    from backend.pipeline.summarizer import PoliteratePipeline
    from backend.db.cache import save_clusters, update_last_refresh

    logger.info("Starting scheduled pipeline update...")
    try:
        pipeline = PoliteratePipeline(model_path=BART_MODEL_PATH)
        # Reuse the already-loaded global model instead of loading a second copy.
        # Calling pipeline.load_model() while _model is in memory doubles RAM usage
        # and OOMs the server on small droplets.
        if _model is not None:
            pipeline._model = _model
            pipeline._tokenizer = _tokenizer
        else:
            pipeline.load_model()
        results = pipeline.run()

        save_clusters(results.get("clusters", []))
        update_last_refresh()
        logger.info(f"Pipeline update complete. Stats: {results.get('stats', {})}")
        return True
    except Exception:
        logger.exception("Pipeline update failed")
        return False


def scheduled_job():
    if is_stale():
        logger.info("Cache is stale, running pipeline update...")
        run_pipeline_update()
    else:
        logger.info("Cache is fresh, skipping update")


def daily_snapshot_job():
    from backend.db.cache import prune_archive, save_daily_snapshot
    from backend.pipeline.summarizer import LOOKBACK_HOURS
    logger.info("Running end-of-day snapshot job...")
    try:
        save_daily_snapshot()
    except Exception:
        logger.exception("Snapshot job failed")
    response_cache.clear()
    # Downloads past the lookback window can't count toward any story now.
    # This is where health, tech and business articles that never became
    # relevant are finally dropped; until then each run re-checks them.
    try:
        prune_archive(hours=LOOKBACK_HOURS)
    except Exception:
        logger.exception("Pruning old downloads failed")


def start_scheduler():
    scheduler.add_job(
        func=scheduled_job,
        trigger="interval",
        hours=1,
        id="pipeline_refresh",
        name="Refresh summaries hourly",
        replace_existing=True,
    )
    scheduler.add_job(
        func=daily_snapshot_job,
        trigger="cron",
        hour=23,
        minute=55,
        id="daily_snapshot",
        name="End-of-day snapshot",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started - hourly refresh + 23:55 snapshot")


def initialize():
    from datetime import datetime
    import importlib
    importlib.import_module("backend.pipeline.summarizer")

    init_db()
    load_model()
    load_analyzer()
    start_scheduler()

    if is_stale():
        logger.info("Cache is stale on startup - queuing immediate pipeline run...")
        scheduler.get_job("pipeline_refresh").modify(next_run_time=datetime.now(TIMEZONE))

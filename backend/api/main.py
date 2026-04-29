"""
backend/api/main.py

Flask application factory for Politerate. Mirrors Sarah's
`backend/api/main.py` layout: app setup + blueprint registration +
model/scheduler lifecycle in one place.

Run via `python run.py` at the project root.
"""

import logging
import os

from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

from backend.config import (
    BART_MODEL_PATH,
    CORS_ORIGINS,
    STATIC_DIR,
    TEMPLATES_DIR,
)
from backend.db.cache import is_stale
from backend.db.connection import init_db
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state (BART summarizer + scheduler). Kept here so blueprints
# can import it; loaded once in initialize().
# ---------------------------------------------------------------------------
_model = None
_tokenizer = None
scheduler = BackgroundScheduler()


def create_app() -> Flask:
    """Flask app factory. Pins template/static folders to project root so
    Flask finds them regardless of where this module lives in the tree."""
    app = Flask(
        __name__,
        template_folder=str(TEMPLATES_DIR),
        static_folder=str(STATIC_DIR),
    )

    # Permissive CORS for the React dev server (and any future origins set
    # via POLITERATE_CORS_ORIGINS). Only fires when Origin header is set,
    # so server-rendered templates are unaffected.
    @app.after_request
    def _apply_cors(response):
        from flask import request
        origin = request.headers.get("Origin")
        if origin and (origin in CORS_ORIGINS or "*" in CORS_ORIGINS):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

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
    global _model
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
    except Exception as e:
        logger.error(f"Failed to load model: {e}")

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
    from backend.pipeline.summarizer import PoliteratePipeline
    from backend.db.cache import save_clusters, update_last_refresh

    logger.info("Starting scheduled pipeline update...")
    try:
        pipeline = PoliteratePipeline(model_path=BART_MODEL_PATH)
        pipeline.load_model()
        results = pipeline.run()

        save_clusters(results.get("clusters", []))
        update_last_refresh()
        logger.info(f"Pipeline update complete. Stats: {results.get('stats', {})}")
        return True
    except Exception as e:
        logger.error(f"Pipeline update failed: {e}")
        return False


def scheduled_job():
    if is_stale():
        logger.info("Cache is stale, running pipeline update...")
        run_pipeline_update()
    else:
        logger.info("Cache is fresh, skipping update")


def daily_snapshot_job():
    from backend.db.cache import save_daily_snapshot
    logger.info("Running end-of-day snapshot job...")
    try:
        save_daily_snapshot()
    except Exception as e:
        logger.error(f"Snapshot job failed: {e}")


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
    init_db()
    load_model()
    load_analyzer()

    
    if is_stale():
        logger.info("Cache is stale on startup - running initial pipeline...")
        run_pipeline_update()

    start_scheduler()

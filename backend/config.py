"""
Centralized configuration for the Politerate backend.

Every path, model ID, and tunable knob that needs to be shared across
modules lives here so individual files don't hard-code them. Mirrors
Sarah's `backend/config.py` convention on `app_branch`.
"""

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Project root = parent of backend/ = the repo root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

# React/TypeScript frontend build output (`npm run build` in frontend/).
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"

# SQLite cache. Kept at project root so existing DBs aren't orphaned.
DB_PATH = PROJECT_ROOT / "politerate.db"

# Nightly database backups (scripts/backup_db.py). Outside the repo so
# re-cloning or `git clean` can't delete them.
BACKUP_DIR = Path(os.environ.get("POLITERATE_BACKUP_DIR", Path.home() / "politerate_backups"))

# Where the fine-tuned BART summarizer lives locally (for dev machines that
# trained it). Falls back to HF Hub when missing.
BART_LOCAL_DIR = PROJECT_ROOT / "fine_tuned_bart_news"

# DeBERTa analyzer weights. Committed at backend/models/analyzer.pt;
# HF Hub download falls back to the same directory.
INFERENCE_WEIGHTS_DIR = PROJECT_ROOT / "backend" / "models"
DEFAULT_ANALYZER_WEIGHTS = INFERENCE_WEIGHTS_DIR / "analyzer.pt"

# ---------------------------------------------------------------------------
# Hugging Face model IDs
# ---------------------------------------------------------------------------
HF_BART_MODEL_ID = "sameersethuram/politerate-bart-news"
HF_ANALYZER_MODEL_ID = "ssimbulan25/politerateArticleAnalyzer"
HF_ANALYZER_WEIGHTS_FILE = "analyzer.pt"

# ---------------------------------------------------------------------------
# Runtime knobs
# ---------------------------------------------------------------------------
# Priority: explicit env var > local dir (if it exists) > HF Hub fallback.
BART_MODEL_PATH = (
    os.environ.get("POLITERATE_MODEL")
    or (str(BART_LOCAL_DIR) if BART_LOCAL_DIR.exists() else HF_BART_MODEL_ID)
)

DEVICE = os.environ.get("POLITERATE_DEVICE", "cpu")

CORS_ORIGINS = os.environ.get(
    "POLITERATE_CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

CACHE_MAX_AGE_HOURS = int(os.environ.get("POLITERATE_CACHE_HOURS", "1"))

CREDIBILITY_THRESHOLD = float(os.environ.get("POLITERATE_CREDIBILITY_THRESHOLD", "0.6"))

# The site's clock, whatever the server's own time zone (DigitalOcean
# droplets run on UTC, which made the day change at 8 p.m. Eastern). It
# decides what "today" is (the feeds' articles, the live topics, the Articles
# page's days, archive dates), when the end-of-day snapshot runs, and the
# stored timestamps. America/New_York switches between EST and EDT.
TIMEZONE = ZoneInfo(os.environ.get("POLITERATE_TIMEZONE", "America/New_York"))


def site_now() -> datetime:
    """The current time on the site's clock, without a zone attached: the
    form timestamps are stored in, so SQLite's date() and plain string
    comparisons read them as the site's dates and times."""
    return datetime.now(TIMEZONE).replace(tzinfo=None)


def analyzer_weights_path() -> Path:
    """Resolve the analyzer weights path, honoring POLITERATE_CREDIBILITY_WEIGHTS."""
    override = os.environ.get("POLITERATE_CREDIBILITY_WEIGHTS")
    return Path(override) if override else DEFAULT_ANALYZER_WEIGHTS

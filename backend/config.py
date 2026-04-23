"""Centralized configuration for the Politerate backend."""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.resolve()

# === Paths ===
MODEL_WEIGHTS_PATH = os.getenv(
    "MODEL_WEIGHTS_PATH",
    str(BACKEND_DIR / "models" / "analyzer.pt")
)

DB_PATH = os.getenv(
    "DB_PATH",
    str(BACKEND_DIR / "data" / "politerate.db")
)

# === Model ===
DEVICE = os.getenv("DEVICE", "cpu")
MODEL_VERSION = "politerate-v1"

# === API ===
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:5174"
).split(",")

# === Limits ===
MIN_ARTICLE_LENGTH = int(os.getenv("MIN_ARTICLE_LENGTH", "50"))
MAX_ARTICLE_LENGTH = int(os.getenv("MAX_ARTICLE_LENGTH", "50000"))

# === Logging ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
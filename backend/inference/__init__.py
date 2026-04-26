"""
Credibility / bias analyzer package.

Provides `get_analyzer()` which returns the multi-head DeBERTa analyzer
(real one if weights are available locally or on HF Hub, else a
MockAnalyzer). Ported from Sarah's `backend/inference/`.

The pipeline-level credibility filter (CredibilityChecker,
filter_by_credibility) lives in `backend/pipeline/credibility.py`; that
module routes through `get_analyzer()` to derive a credibility score
from the analyzer's per-article predictions.
"""

import logging
import os
from pathlib import Path

from ..config import (
    analyzer_weights_path,
    DEVICE,
    HF_ANALYZER_MODEL_ID,
    HF_ANALYZER_WEIGHTS_FILE,
    INFERENCE_WEIGHTS_DIR,
)

logger = logging.getLogger(__name__)

_analyzer_instance = None


def _resolve_weights_file() -> Path | None:
    """Return a usable path to analyzer.pt, downloading from HF Hub if needed.

    Resolution order:
      1. Local file at analyzer_weights_path() (honors env override).
      2. Attempt huggingface_hub.hf_hub_download(HF_ANALYZER_MODEL_ID).
      3. None — caller falls back to MockAnalyzer.
    """
    local = analyzer_weights_path()
    if local.is_file():
        return local

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        logger.warning("huggingface_hub not installed; cannot fetch analyzer weights")
        return None

    try:
        INFERENCE_WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Downloading analyzer weights from HF Hub (%s/%s)...",
            HF_ANALYZER_MODEL_ID, HF_ANALYZER_WEIGHTS_FILE,
        )
        cached = hf_hub_download(
            repo_id=HF_ANALYZER_MODEL_ID,
            filename=HF_ANALYZER_WEIGHTS_FILE,
            local_dir=str(INFERENCE_WEIGHTS_DIR),
        )
        return Path(cached)
    except Exception as e:
        logger.warning("Failed to download analyzer weights from HF Hub: %s", e)
        return None


def get_analyzer():
    """Return a cached analyzer instance. Uses PoliterateAnalyzer when
    weights are available (local or HF Hub), otherwise MockAnalyzer."""
    global _analyzer_instance
    if _analyzer_instance is not None:
        return _analyzer_instance

    weights = _resolve_weights_file()
    if weights and weights.is_file():
        try:
            from .predictor import PoliterateAnalyzer
            logger.info(f"Loading PoliterateAnalyzer from {weights}")
            _analyzer_instance = PoliterateAnalyzer(
                weights_path=str(weights),
                device=DEVICE,
            )
            return _analyzer_instance
        except Exception as e:
            logger.warning(
                "Failed to load real PoliterateAnalyzer (%s); falling back to MockAnalyzer",
                e,
            )

    logger.info("No usable credibility weights found - using MockAnalyzer")
    from .mock import MockAnalyzer
    _analyzer_instance = MockAnalyzer()
    return _analyzer_instance


def reset_analyzer():
    """Drop the cached analyzer so `get_analyzer()` will re-initialize."""
    global _analyzer_instance
    _analyzer_instance = None

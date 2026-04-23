"""
Credibility / bias analyzer package.

Two interfaces live here:

1. `get_analyzer()` — returns the multi-head DeBERTa analyzer (real one
   if weights are in `credibility/weights/analyzer.pt`, else a
   MockAnalyzer). Used by `/api/analyze` to power the Text Analyzer
   page. Ported from Sarah's `backend/inference/` work.

2. `check_credibility(article)` / `filter_by_credibility(articles)` —
   the article-filtering interface the news pipeline calls during
   scraping. Currently returns the stub pass-through (all articles
   pass) while weights are pending; once BUG-3 lands, this can be
   wired through `get_analyzer().predict_article()` to derive a real
   credibility score.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
DEFAULT_WEIGHTS_PATH = WEIGHTS_DIR / "analyzer.pt"
CREDIBILITY_THRESHOLD = 0.6

_analyzer_instance = None


def _weights_path() -> Path:
    override = os.environ.get("POLITERATE_CREDIBILITY_WEIGHTS")
    return Path(override) if override else DEFAULT_WEIGHTS_PATH


def get_analyzer():
    """Return a cached analyzer instance. Uses the real PoliterateAnalyzer
    if weights are present, otherwise a MockAnalyzer."""
    global _analyzer_instance
    if _analyzer_instance is not None:
        return _analyzer_instance

    weights = _weights_path()
    if weights.is_file():
        try:
            from .predictor import PoliterateAnalyzer
            logger.info(f"Loading PoliterateAnalyzer from {weights}")
            _analyzer_instance = PoliterateAnalyzer(
                weights_path=str(weights),
                device=os.environ.get("POLITERATE_DEVICE", "cpu"),
            )
            return _analyzer_instance
        except Exception as e:
            logger.warning(
                "Failed to load real PoliterateAnalyzer (%s); falling back to MockAnalyzer",
                e,
            )

    logger.info("No credibility weights at %s — using MockAnalyzer", weights)
    from .mock import MockAnalyzer
    _analyzer_instance = MockAnalyzer()
    return _analyzer_instance


def reset_analyzer():
    """Drop the cached analyzer so `get_analyzer()` will re-initialize."""
    global _analyzer_instance
    _analyzer_instance = None


# ==================================================================
# Legacy pipeline-filter interface (replaces the old top-level
# credibility.py module). Preserved so pipeline.py keeps working.
# ==================================================================

class CredibilityChecker:
    def __init__(self, threshold: float = CREDIBILITY_THRESHOLD):
        self.threshold = threshold
        self._impl = self._resolve_impl()

    def _resolve_impl(self):
        analyzer = get_analyzer()
        version = getattr(analyzer, "model_version", "unknown")
        logger.info(f"CredibilityChecker routing through analyzer ({version})")
        return lambda text: self._analyzer_impl(analyzer, text)

    @staticmethod
    def _analyzer_impl(analyzer, text: str) -> dict:
        """Derive a credibility dict from analyzer.predict_article() output.
        score = 1 - subjectivity_ratio (more loaded/emotional = less credible)."""
        result = analyzer.predict_article(text)
        article = result.get("article") or {}
        subj = float(article.get("subjectivity_ratio") or 0.0)
        score = max(0.0, min(1.0, 1.0 - subj))

        technique_counts = article.get("technique_counts") or {}
        top_techniques = sorted(technique_counts.items(), key=lambda x: -x[1])[:3]
        reasons = [label.replace("_", " ") for label, _ in top_techniques] or ["no persuasion techniques detected"]

        chunks = result.get("chunks") or []
        confidence = min(1.0, len(chunks) / 10.0) if chunks else 0.0

        return {
            "score": score,
            "flag": score < CREDIBILITY_THRESHOLD,
            "reasons": reasons,
            "bias_label": article.get("dominant_bias") or "unknown",
            "confidence": round(confidence, 3),
        }

    def check(self, article: dict) -> dict:
        text = article.get("text", "")
        url = article.get("url", "unknown")

        if not text:
            logger.warning(f"{url}: empty text, skipping credibility check")
            return {
                "score": 0.0,
                "flag": True,
                "reasons": ["empty text"],
                "bias_label": "unknown",
                "confidence": 0.0,
                "url": url,
                "passed": False,
            }

        try:
            result = self._impl(text)
            result["url"] = url
            result["passed"] = result["score"] >= self.threshold
            return result
        except Exception as e:
            logger.error(f"Credibility check failed for {url}: {type(e).__name__}: {str(e)[:50]}")
            return {
                "score": 0.0,
                "flag": True,
                "reasons": [f"check failed: {str(e)[:30]}"],
                "bias_label": "unknown",
                "confidence": 0.0,
                "url": url,
                "passed": False,
            }

    def filter_articles(self, articles: list[dict]) -> tuple[list[dict], list[dict]]:
        passed, failed = [], []
        logger.info(f"Checking credibility of {len(articles)} articles")
        for article in articles:
            result = self.check(article)
            article["credibility"] = result
            (passed if result["passed"] else failed).append(article)
            if not result["passed"]:
                logger.info(f"Filtered {article.get('url', 'unknown')}: {result['reasons']}")
        logger.info(f"Credibility filter: {len(passed)} passed, {len(failed)} failed")
        return passed, failed


def check_credibility(article: dict) -> dict:
    return CredibilityChecker().check(article)


def filter_by_credibility(articles: list[dict]) -> tuple[list[dict], list[dict]]:
    return CredibilityChecker().filter_articles(articles)

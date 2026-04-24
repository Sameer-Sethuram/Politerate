"""
Pipeline-level credibility filter.

Gates scraped articles before they enter clustering. Routes through
`backend.inference.get_analyzer()` so the same DeBERTa model that powers
the Text Analyzer page also scores the news feed. When weights aren't
available, MockAnalyzer scores articles via content heuristics so the
pipeline keeps running end-to-end.

Public API (preserved from the old top-level `credibility.py`):
    CredibilityChecker
    check_credibility(article) -> dict
    filter_by_credibility(articles) -> (passed, failed)
"""

import logging

from backend.config import CREDIBILITY_THRESHOLD
from backend.inference import get_analyzer

logger = logging.getLogger(__name__)


class CredibilityChecker:
    def __init__(self, threshold: float = CREDIBILITY_THRESHOLD):
        self.threshold = threshold
        self._impl = self._resolve_impl()

    def _resolve_impl(self):
        analyzer = get_analyzer()
        version = getattr(analyzer, "model_version", "unknown")
        logger.info(f"CredibilityChecker routing through analyzer ({version})")
        return lambda text: self._analyzer_impl(analyzer, text)

    def _analyzer_impl(self, analyzer, text: str) -> dict:
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
            "flag": score < self.threshold,
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

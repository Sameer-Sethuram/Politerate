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

    def _analyzer_impl(self, analyzer, text: str) -> tuple[dict, dict]:
        """Returns (credibility_dict, full_analyzer_result).

        score = 1 - subjectivity_ratio (more loaded/emotional = less credible).
        The full result carries chunk-level predictions for downstream storage."""
        result = analyzer.predict_article(text)
        article = result.get("article") or {}
        subj = float(article.get("subjectivity_ratio") or 0.0)
        score = max(0.0, min(1.0, 1.0 - subj))

        technique_counts = article.get("technique_counts") or {}
        top_techniques = sorted(technique_counts.items(), key=lambda x: -x[1])[:3]
        reasons = (
            [label.replace("_", " ") for label, _ in top_techniques]
            or ["no persuasion techniques detected"]
        )

        chunks = result.get("chunks") or []
        confidence = min(1.0, len(chunks) / 10.0) if chunks else 0.0

        credibility = {
            "score": score,
            "flag": score < self.threshold,
            "reasons": reasons,
            "bias_label": article.get("dominant_bias") or "unknown",
            "confidence": round(confidence, 3),
        }
        return credibility, result

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
            credibility, _ = self._impl(text)
            credibility["url"] = url
            credibility["passed"] = credibility["score"] >= self.threshold
            return credibility
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
            text = article.get("text", "")
            url = article.get("url", "unknown")

            if not text:
                article["credibility"] = {
                    "score": 0.0,
                    "flag": True,
                    "reasons": ["empty text"],
                    "bias_label": "unknown",
                    "confidence": 0.0,
                    "url": url,
                    "passed": False,
                }
                failed.append(article)
                continue

            try:
                credibility, full_result = self._impl(text)
                credibility["url"] = url
                credibility["passed"] = credibility["score"] >= self.threshold
                article["credibility"] = credibility
                article["_analysis"] = full_result
            except Exception as e:
                logger.error(f"Credibility check failed for {url}: {type(e).__name__}: {str(e)[:50]}")
                article["credibility"] = {
                    "score": 0.0,
                    "flag": True,
                    "reasons": [f"check failed: {str(e)[:30]}"],
                    "bias_label": "unknown",
                    "confidence": 0.0,
                    "url": url,
                    "passed": False,
                }

            (passed if article["credibility"]["passed"] else failed).append(article)
            if not article["credibility"]["passed"]:
                logger.info(f"Filtered {url}: {article['credibility']['reasons']}")

        logger.info(f"Credibility filter: {len(passed)} passed, {len(failed)} failed")
        return passed, failed


def check_credibility(article: dict) -> dict:
    return CredibilityChecker().check(article)


def filter_by_credibility(articles: list[dict]) -> tuple[list[dict], list[dict]]:
    return CredibilityChecker().filter_articles(articles)

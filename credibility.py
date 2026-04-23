"""
credibility.py

Interface for article credibility checking.
Integrates with Sarah's sentiment analysis pipeline for political bias detection.

Interface:
    check_credibility(article_text: str) -> dict:
        Returns: {"score": float, "flag": bool, "reasons": list, "bias_label": str}

Usage:
    Stub mode (default): All articles pass.
    Sarah integrates her Deberta-v3 model by implementing check_credibility_impl().
"""

import logging
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

CREDIBILITY_THRESHOLD = 0.6


class CredibilityChecker:
    def __init__(self, threshold: float = CREDIBILITY_THRESHOLD):
        self.threshold = threshold
        self._impl = None
        self._init_impl()

    def _init_impl(self):
        try:
            from credibility_impl import check_article_credibility
            self._impl = check_article_credibility
            logger.info("Loaded custom credibility implementation")
        except ImportError:
            self._impl = self._stub_impl
            logger.info("Using stub credibility checker (no custom impl found)")

    def _stub_impl(self, text: str) -> dict:
        return {
            "score": 1.0,
            "flag": False,
            "reasons": ["stub mode - no credibility analysis"],
            "bias_label": "unknown",
            "confidence": 0.0
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
                "confidence": 0.0
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
                "passed": False
            }

    def filter_articles(self, articles: list[dict]) -> tuple[list[dict], list[dict]]:
        passed = []
        failed = []

        logger.info(f"Checking credibility of {len(articles)} articles")

        for article in articles:
            result = self.check(article)
            article["credibility"] = result

            if result["passed"]:
                passed.append(article)
            else:
                failed.append(article)
                logger.info(f"Filtered {article.get('url', 'unknown')}: {result['reasons']}")

        logger.info(f"Credibility filter: {len(passed)} passed, {len(failed)} failed")
        return passed, failed


def check_credibility(article: dict) -> dict:
    checker = CredibilityChecker()
    return checker.check(article)


def filter_by_credibility(articles: list[dict]) -> tuple[list[dict], list[dict]]:
    checker = CredibilityChecker()
    return checker.filter_articles(articles)


if __name__ == "__main__":
    test_articles = [
        {
            "title": "Balanced Report",
            "text": "The Senate voted on the bill today. Supporters say it will help the economy while critics argue there are concerns about implementation costs.",
            "url": "https://example.com/balanced",
            "source": "AP"
        },
        {
            "title": "Extremely Biased",
            "text": "The MAGA radicals in Congress are DESTROYING our country! These evil fascists want to steal your freedom and destroy everything America stands for! SHAME on them!",
            "url": "https://example.com/bias",
            "source": "ExtremistNews"
        },
        {
            "title": "Neutral Tech Article",
            "text": "Apple announced quarterly earnings today. Revenue increased by 5% compared to the same quarter last year. The company did not provide detailed guidance for the next quarter.",
            "url": "https://example.com/tech",
            "source": "TechDaily"
        }
    ]

    print("\n=== Credibility Check Test ===")
    checker = CredibilityChecker()
    for article in test_articles:
        result = checker.check(article)
        print(f"\n[{article['source']}] {article['title']}")
        print(f"  Score: {result['score']:.2f}")
        print(f"  Passed: {result['passed']}")
        print(f"  Reasons: {result['reasons']}")

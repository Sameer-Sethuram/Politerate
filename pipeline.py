"""
pipeline.py

Orchestrates the full Politerate pipeline:
1. Scrape articles from RSS feeds
2. Preprocess text
3. Cluster by topic
4. Filter by credibility
5. Summarize (when model is ready)
6. Highlight political terms

Usage:
    from pipeline import run_pipeline
    results = run_pipeline()
"""

import logging
from typing import Optional

from preprocessor import preprocess_batch
from clustering import cluster_articles, ArticleClusterer
from credibility import filter_by_credibility
from politerate import TermHighlighter

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class PoliteratePipeline:
    def __init__(
        self,
        model_path: Optional[str] = None,
        similarity_threshold: float = 0.40,
        min_cluster_size: int = 2,
        credibility_threshold: float = 0.6
    ):
        self.model_path = model_path
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.credibility_threshold = credibility_threshold

        self.clusterer = None
        self.highlighter = TermHighlighter()

        self._model = None
        self._tokenizer = None

    def scrape(self) -> dict:
        logger.info("Step 1: Scraping articles...")
        try:
            from rss_link_scraper import get_all_top_story_links
            from webscraper import scrape_articles_by_source
        except ImportError as e:
            logger.error(f"Import error: {e}")
            return {}

        links = get_all_top_story_links()
        articles = scrape_articles_by_source(links)
        logger.info(f"Scraped articles from {len(articles)} sources")
        return articles

    def preprocess(self, articles: list[dict]) -> list[dict]:
        logger.info("Step 2: Preprocessing articles...")
        processed = preprocess_batch(articles)
        logger.info(f"Preprocessed {len(processed)} articles")
        return processed

    def cluster(self, articles: list[dict]) -> dict:
        logger.info("Step 3: Clustering articles by topic...")
        self.clusterer = ArticleClusterer(
            similarity_threshold=self.similarity_threshold,
            min_cluster_size=self.min_cluster_size
        )
        clusters = self.clusterer.cluster(articles)
        logger.info(f"Created {len(clusters)} topic clusters")
        return clusters

    def filter_credibility(self, articles: list[dict]) -> tuple[list[dict], list[dict]]:
        logger.info("Step 4: Filtering by credibility...")
        passed, failed = filter_by_credibility(articles)
        logger.info(f"Credibility filter: {len(passed)} passed, {len(failed)} filtered")
        return passed, failed

    def summarize(self, text: str) -> str:
        if not self._model:
            logger.warning("Summarization model not loaded - returning placeholder")
            return "[Summary unavailable - model not loaded]"

        from transformers import GenerationConfig
        inputs = self._tokenizer(
            text,
            max_length=1024,
            truncation=True,
            return_tensors="pt"
        )

        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        inputs = {k: v.to(device) for k, v in inputs.items()}

        outputs = self._model.generate(
            **inputs,
            max_length=150,
            min_length=50,
            num_beams=4,
            early_stopping=True
        )

        return self._tokenizer.decode(outputs[0], skip_special_tokens=True)

    def load_model(self, path: str = None) -> None:
        path = path or self.model_path
        if not path:
            logger.warning("No model path provided - summarization will use placeholder")
            return

        try:
            logger.info(f"Loading summarization model from {path}...")
            from transformers import BartForConditionalGeneration, BartTokenizer
            self._tokenizer = BartTokenizer.from_pretrained(path)
            self._model = BartForConditionalGeneration.from_pretrained(path)
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = self._model.to(device)
            self._model.eval()
            logger.info(f"Model loaded on {device}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self._model = None

    def highlight_terms(self, text: str) -> str:
        return self.highlighter.highlight(text)

    def create_daily_summary(self, clusters: list[dict]) -> str:
        """Create a unified daily summary from all clusters with automatic transitions."""
        if not clusters:
            return "[No significant news clusters available today]"

        sorted_clusters = sorted(clusters, key=lambda x: x.get("article_count", 0), reverse=True)

        summary_segments = []
        for i, cluster in enumerate(sorted_clusters):
            summary = cluster.get("summary", "")
            if not summary or summary.startswith("["):
                continue

            if i == 0:
                summary_segments.append(summary)
            else:
                transition_phrases = [
                    "Additionally,",
                    "Meanwhile,",
                    "In related news,",
                    "Separately,",
                    "On another topic,"
                ]
                transition = transition_phrases[i % len(transition_phrases)]
                summary_segments.append(f"{transition} {summary.lower()}")

        if not summary_segments:
            return "[Summary unavailable - check back later]"

        return " ".join(summary_segments)

    def get_daily_summary_data(self, clusters: list[dict]) -> dict:
        """Get all data needed for the daily summary view."""
        filtered_clusters = [
            c for c in clusters
            if not str(c.get("cluster_id", "")).startswith("singleton_")
            and c.get("article_count", 0) >= 2
        ]

        all_sources = set()
        all_article_count = 0
        for cluster in filtered_clusters:
            all_sources.update(cluster.get("sources", []))
            all_article_count += cluster.get("article_count", 0)

        return {
            "unified_summary": self.create_daily_summary(filtered_clusters),
            "highlighted_summary": self.highlighter.highlight(self.create_daily_summary(filtered_clusters)),
            "cluster_count": len(filtered_clusters),
            "source_count": len(all_sources),
            "total_articles": all_article_count,
            "clusters": filtered_clusters
        }

    def process_clusters(self, clusters: dict) -> list[dict]:
        results = []

        for cluster_id, articles in clusters.items():
            if str(cluster_id).startswith("singleton_"):
                continue
            if len(articles) < 2:
                continue

            cluster_text = " ".join(a.get("text", "") for a in articles)
            sources = list(set(a.get("source", "unknown") for a in articles))

            summary = self.summarize(cluster_text)
            highlighted_summary = self.highlight_terms(summary)
            terms = self.highlighter.get_term_definitions(summary)

            results.append({
                "cluster_id": cluster_id,
                "article_count": len(articles),
                "sources": sources,
                "urls": [a.get("url") for a in articles],
                "titles": [a.get("title") for a in articles],
                "summary": summary,
                "highlighted_summary": highlighted_summary,
                "defined_terms": terms,
                "articles": articles
            })

        return results

    def _build_raw_articles_with_dedup(self) -> dict:
        """Fetch RSS links, download only new URLs, merge with archive. Returns {source: {url: article}}."""
        try:
            from rss_link_scraper import get_all_top_story_links
            from webscraper import scrape_articles_by_source
        except ImportError as e:
            logger.error(f"Import error: {e}")
            return {}

        from cache import (
            filter_unseen_urls,
            mark_urls_seen,
            archive_articles,
            get_archived_articles,
            prune_archive,
        )

        prune_archive(days=7)

        links_by_source = get_all_top_story_links()
        all_urls = [u for urls in links_by_source.values() for u in urls]
        unseen = set(filter_unseen_urls(all_urls))

        logger.info(f"RSS URLs total={len(all_urls)}, unseen={len(unseen)}")

        if unseen:
            new_links = {
                s: [u for u in urls if u in unseen]
                for s, urls in links_by_source.items()
            }
            new_links = {s: urls for s, urls in new_links.items() if urls}

            logger.info(f"Downloading {sum(len(v) for v in new_links.values())} new articles")
            newly_scraped = scrape_articles_by_source(new_links)

            flat_new = []
            for source, url_to_article in newly_scraped.items():
                for url, article in url_to_article.items():
                    if article is None:
                        continue
                    article["source"] = source
                    article["url"] = url
                    flat_new.append(article)

            if flat_new:
                archive_articles(flat_new)
                mark_urls_seen([a["url"] for a in flat_new])
        else:
            logger.info("No new URLs — serving entirely from archive")

        archived = get_archived_articles(all_urls)

        raw_articles = {}
        for source, urls in links_by_source.items():
            source_dict = {}
            for url in urls:
                if url in archived:
                    art = archived[url].copy()
                    art["source"] = source
                    source_dict[url] = art
            if source_dict:
                raw_articles[source] = source_dict

        return raw_articles

    def run(self, scraped_articles: dict = None) -> dict:
        logger.info("Starting Politerate Pipeline")

        if self.model_path and not self._model:
            self.load_model()

        if scraped_articles is not None:
            raw_articles = scraped_articles
        else:
            raw_articles = self._build_raw_articles_with_dedup()

        flat_articles = []
        for source, articles in raw_articles.items():
            for url, article in articles.items():
                article["source"] = source
                flat_articles.append(article)

        if not flat_articles:
            logger.warning("No articles to process")
            return {"clusters": [], "stats": {"total": 0}}

        processed = self.preprocess(flat_articles)

        passed, failed = self.filter_credibility(processed)

        clusters = self.cluster(passed)

        results = self.process_clusters(clusters)

        stats = {
            "total_scraped": len(flat_articles),
            "total_processed": len(processed),
            "passed_credibility": len(passed),
            "filtered_credibility": len(failed),
            "total_clusters": len(clusters),
            "clusters_with_summaries": len(results)
        }

        logger.info(f"Pipeline complete: {stats}")

        return {
            "clusters": results,
            "stats": stats
        }


def run_pipeline(model_path: Optional[str] = None, **kwargs) -> dict:
    pipeline = PoliteratePipeline(model_path=model_path, **kwargs)
    return pipeline.run()


if __name__ == "__main__":
    print("\n=== Politerate Pipeline Test ===")
    print("(Using stub components - no model or scraping in test mode)\n")

    test_articles = [
        {
            "title": "President Signs New Climate Bill",
            "text": "President Signs New Climate Bill Congress passed the landmark climate legislation on Tuesday.",
            "url": "https://example.com/climate-bill",
            "source": "CNN"
        },
        {
            "title": "Climate Legislation Update",
            "text": "The new climate bill passed Congress and was signed by the President. Environmental groups praised the legislation.",
            "url": "https://example.com/climate-legislation",
            "source": "NBC"
        },
        {
            "title": "Stock Market Hits Record High",
            "text": "The Dow Jones reached a new record high today as tech stocks continued their rally.",
            "url": "https://example.com/stock-market",
            "source": "Reuters"
        }
    ]

    pipeline = PoliteratePipeline()
    pipeline.clusterer = ArticleClusterer()

    clusters = pipeline.cluster(test_articles)
    passed, failed = pipeline.filter_credibility(test_articles)

    print(f"Clusters: {len(clusters)}")
    print(f"Credibility: {len(passed)} passed, {len(failed)} filtered")

    results = pipeline.process_clusters(clusters)
    print(f"\nProcessed {len(results)} cluster summaries:\n")

    for result in results:
        print(f"Cluster {result['cluster_id']} ({result['article_count']} articles):")
        print(f"  Sources: {result['sources']}")
        print(f"  Summary: {result['summary']}")
        if result['defined_terms']:
            print(f"  Terms: {[t['term'] for t in result['defined_terms']]}")
        print()

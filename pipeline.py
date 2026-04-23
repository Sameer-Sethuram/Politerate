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
import re
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


# Tune from here. A cluster must have >= MIN_ARTICLES_PER_CLUSTER to be in the
# daily brief; at most MAX_CLUSTERS_IN_DAILY_BRIEF survive (used for topic cards),
# and MAX_CLUSTERS_IN_BRIEF_INPUT caps what we actually feed to the hierarchical
# BART pass — keeping the input short avoids degenerate generation when BART
# runs out of coherent things to say.
MIN_ARTICLES_PER_CLUSTER = 3
MAX_CLUSTERS_IN_DAILY_BRIEF = 8
MAX_CLUSTERS_IN_BRIEF_INPUT = 5

# Conditional generation tiers: (source_token_threshold, (max_length, min_length)).
# Scales BART output budget to the size of the source material. Prevents
# hallucination on thin clusters (small source -> short target) while still
# giving rich clusters room to breathe. Measured against the PRE-truncation
# token count, not BART's 1024-cap input.
_SOURCE_BUDGET_TIERS = [
    (1200,           (140, 40)),   # ~1 short article
    (2800,           (200, 70)),   # ~2 articles
    (5500,           (240, 100)),  # ~3-5 articles
    (float("inf"),   (280, 130)),  # rich cluster
]
# Threshold above which the truncation retry is allowed to use aggressive
# params (early_stopping=False, higher min_length). Below this, the retry
# stays conservative to avoid forcing hallucination.
_RICH_SOURCE_THRESHOLD = 2800


def _budget_for_source(token_count: int) -> tuple[int, int]:
    for threshold, budget in _SOURCE_BUDGET_TIERS:
        if token_count < threshold:
            return budget
    return _SOURCE_BUDGET_TIERS[-1][1]


_CAMEL_BOUNDARY = re.compile(r"[a-z][A-Z]")


def _looks_garbled(text: str) -> bool:
    """Detect BART degenerate output. Heuristic: more than a few camel-case
    boundaries (e.g. "BanksCloseagnSteam") inside a single summary is a strong
    signal that the decoder fell off into low-probability token space.
    """
    if not text:
        return False
    return len(_CAMEL_BOUNDARY.findall(text)) >= 4


def _strip_garbled_tail(text: str) -> str:
    """Salvage the coherent prefix of a garbled BART output by trimming at
    the last sentence end before the first camelCase anomaly.
    """
    if not text:
        return text
    m = _CAMEL_BOUNDARY.search(text)
    if not m:
        return text
    prefix = text[: m.start()]
    last_end = max(prefix.rfind("."), prefix.rfind("!"), prefix.rfind("?"))
    if last_end > 0:
        return prefix[: last_end + 1].strip()
    return prefix.strip()


def _looks_truncated(text: str) -> bool:
    """True when BART's output appears to have been cut off mid-sentence at
    an abbreviation (e.g. "...slipped by a U.S.").

    Heuristic: a single-sentence output ending in an abbreviation pattern
    means BART hit max_length before emitting a real sentence end. Multi-
    sentence outputs are fine because _clean_bart_output already drops
    trailing abbrev-only fragments when other sentences exist.
    """
    if not text:
        return False
    stripped = text.rstrip()
    if not stripped.endswith("."):
        return False
    sentences = _smart_sentence_split(stripped)
    if len(sentences) > 1:
        return False
    return bool(_ABBREV_END.search(stripped))


_SENTENCE_END = re.compile(r"(?<![.!?])[.!?](?![.!?])")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_ABBREV_END = re.compile(r"\b[A-Z][a-zA-Z-]{0,4}\.$")
MIN_SENT_WORDS = 4


def _smart_sentence_split(text: str) -> list[str]:
    """Sentence-split but merge fragments that end in an abbreviation into
    the next fragment (e.g. "Rep." + "Chris Murphy said..." → one sentence).

    Treats a "short capitalized word + ." (≤5 letters) as abbreviation —
    catches Rep./Sen./Gov./Dr./Mr./U.S./D-Fla./etc. without maintaining a
    static dictionary.
    """
    parts = _SENTENCE_SPLIT.split(text)
    merged: list[str] = []
    i = 0
    while i < len(parts):
        current = parts[i]
        while _ABBREV_END.search(current.rstrip()) and i + 1 < len(parts):
            i += 1
            current = current + " " + parts[i]
        merged.append(current)
        i += 1
    return merged


def _clean_bart_output(text: str) -> str:
    """Fix BART tokenizer artifacts and drop incomplete trailing sentences.

    Pipeline:
      1. Collapse ` .` → `.` artifacts and trailing ellipsis.
      2. Abbreviation-aware sentence split.
      3. Drop trailing fragments — sentences that lack a terminator, end in
         a truncated-abbreviation tail, or are abnormally short.
      4. If the surviving text has no sentence-ending punctuation (common
         when BART hit max_length mid-sentence and we kept the one
         sentence), append a period so the card reads cleanly.
    """
    if not text:
        return text

    text = re.sub(r"\s+([.!?,;:])", r"\1", text)
    text = re.sub(r"\s*\.{2,}\s*$", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()

    sentences = _smart_sentence_split(text)
    while len(sentences) > 1:
        last = sentences[-1].rstrip()
        has_terminator = bool(last) and last[-1] in ".!?"
        is_abbrev_end = bool(_ABBREV_END.search(last))
        is_too_short = len(last.split()) < MIN_SENT_WORDS
        if (not has_terminator) or is_abbrev_end or is_too_short:
            sentences.pop()
        else:
            break

    text = " ".join(sentences).strip()
    if text and text[-1] not in ".!?":
        text = text + "."
    return text


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

    def _bart_generate(
        self,
        text: str,
        max_length: int,
        min_length: int,
        length_penalty: float = 1.1,
        early_stopping: bool = True,
    ) -> str:
        inputs = self._tokenizer(
            text,
            max_length=1024,
            truncation=True,
            return_tensors="pt",
        )
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        inputs = {k: v.to(device) for k, v in inputs.items()}
        outputs = self._model.generate(
            **inputs,
            max_length=max_length,
            min_length=min_length,
            num_beams=6,
            no_repeat_ngram_size=3,
            length_penalty=length_penalty,
            early_stopping=early_stopping,
        )
        return self._tokenizer.decode(outputs[0], skip_special_tokens=True)

    def _salvage_if_garbled(self, cleaned: str) -> str:
        """If `cleaned` is garbled, try to rescue the coherent prefix in-place.
        Returns the salvaged string (possibly still garbled) or `cleaned` as-is."""
        if not _looks_garbled(cleaned):
            return cleaned
        salvaged = _clean_bart_output(_strip_garbled_tail(cleaned))
        if salvaged and not _looks_garbled(salvaged) and len(salvaged.split()) >= MIN_SENT_WORDS:
            return salvaged
        return cleaned

    def _source_token_count(self, text: str) -> int:
        """Measure raw tokenized length of the source (not truncated to 1024)."""
        if self._tokenizer is None or not text:
            return 0
        try:
            return len(self._tokenizer.encode(text, add_special_tokens=False, truncation=False))
        except Exception:
            return 0

    def summarize(
        self,
        text: str,
        max_length: Optional[int] = None,
        min_length: Optional[int] = None,
    ) -> str:
        """Summarize with conditional generation + anti-garbage safeguards.

        Budget scales to source size (via _budget_for_source) unless the
        caller explicitly passes max_length / min_length. This prevents
        hallucination on thin clusters — small source -> short target.

        Flow (hard-capped at two BART calls):
          1. Primary attempt at the tier-appropriate budget.
          2. Always try to salvage garbled output in-place (no extra BART call).
          3. If still garbled OR truncated at an abbreviation, ONE retry
             with params that scale with source richness:
               - Rich source (>= _RICH_SOURCE_THRESHOLD tokens): aggressive —
                 early_stopping=False, higher min_length, longer length penalty.
               - Thin source: conservative — keep early_stopping on, modest
                 budget bump. Avoids forcing BART to invent content.
          4. Accept the retry only if it's strictly better; otherwise keep
             the original cleaned output.
        """
        if not self._model:
            logger.warning("Summarization model not loaded - returning placeholder")
            return "[Summary unavailable - model not loaded]"

        source_tokens = self._source_token_count(text)
        auto_max, auto_min = _budget_for_source(source_tokens)
        effective_max = max_length if max_length is not None else auto_max
        effective_min = min_length if min_length is not None else auto_min

        cleaned = _clean_bart_output(
            self._bart_generate(text, effective_max, effective_min)
        )
        cleaned = self._salvage_if_garbled(cleaned)

        is_garbled = _looks_garbled(cleaned)
        is_truncated = _looks_truncated(cleaned)

        if not is_garbled and not is_truncated:
            return cleaned

        rich_source = source_tokens >= _RICH_SOURCE_THRESHOLD
        logger.warning(
            "Retry (tokens=%d, rich=%s, garbled=%s, truncated=%s)",
            source_tokens, rich_source, is_garbled, is_truncated,
        )

        retry = _clean_bart_output(self._bart_generate(
            text,
            max_length=effective_max + 140,
            min_length=(
                max(effective_min + 40, 120) if rich_source
                else effective_min + 20
            ),
            length_penalty=1.4 if rich_source else 1.2,
            early_stopping=not rich_source,
        ))
        retry = self._salvage_if_garbled(retry)

        if not _looks_garbled(retry) and not _looks_truncated(retry) \
                and len(retry.split()) >= MIN_SENT_WORDS:
            return retry
        return cleaned

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

    def _select_brief_clusters(self, clusters: list[dict]) -> list[dict]:
        eligible = [
            c for c in clusters
            if not str(c.get("cluster_id", "")).startswith("singleton_")
            and c.get("article_count", 0) >= MIN_ARTICLES_PER_CLUSTER
        ]
        eligible.sort(key=lambda c: c.get("article_count", 0), reverse=True)
        return eligible[:MAX_CLUSTERS_IN_DAILY_BRIEF]

    def create_daily_summary(self, clusters: list[dict]) -> str:
        """Build a coherent daily brief via hierarchical summarization.

        Strategy:
          1. Pick the top N clusters by article count (filtering singletons
             and small clusters via MIN_ARTICLES_PER_CLUSTER / MAX_...).
          2. If the model is loaded, feed the top MAX_CLUSTERS_IN_BRIEF_INPUT
             per-cluster summaries back through BART for a unified brief.
          3. If no model or BART produces garbage, fall back to
             cleanly-punctuated concatenation.
        """
        selected = self._select_brief_clusters(clusters)

        segments = []
        for c in selected:
            summary = _clean_bart_output(c.get("summary", ""))
            if summary and not summary.startswith("["):
                segments.append(summary)

        if not segments:
            return "[No significant news clusters available today]"

        concatenated_all = " ".join(segments)
        brief_input = " ".join(segments[:MAX_CLUSTERS_IN_BRIEF_INPUT])

        if self._model:
            try:
                brief = self.summarize(brief_input, max_length=350, min_length=80)
                if brief and not brief.startswith("[") and not _looks_garbled(brief):
                    return brief
                if _looks_garbled(brief):
                    logger.warning("Hierarchical brief looked garbled, falling back to concatenation")
            except Exception as e:
                logger.warning(f"Hierarchical summary failed, falling back: {e}")

        return concatenated_all

    def get_daily_summary_data(self, clusters: list[dict]) -> dict:
        """Get all data needed for the daily summary view."""
        filtered_clusters = [
            c for c in clusters
            if not str(c.get("cluster_id", "")).startswith("singleton_")
            and c.get("article_count", 0) >= MIN_ARTICLES_PER_CLUSTER
        ]
        filtered_clusters.sort(key=lambda c: c.get("article_count", 0), reverse=True)

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

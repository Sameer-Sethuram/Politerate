"""
clustering.py

Groups scraped articles by topic using sentence embeddings.
Uses sentence-transformers for fast, semantic similarity matching.
"""

import logging
from typing import Optional

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# Two articles' similarity blends how close their embeddings are (what they
# mean) with how many distinctive words they share (TF-IDF over the run's
# articles, so a name or place few articles mention counts for a lot and
# words every political story uses, like "Trump" or "midterms", count for
# little). Embeddings alone rate unrelated political stories as fairly
# similar, which merged them into one topic.
EMBEDDING_WEIGHT = 0.6
# Topics are merged while their articles' average blended similarity stays
# at or above this. Scored against hand-labelled stories for ~360 articles
# from one day: embeddings alone put 21 articles in the wrong topic even with
# every pair required to be 0.50 similar (complete linkage); the blend at
# 0.50 put 2, and kept each story in one topic apart from single strays.
DEFAULT_SIMILARITY_THRESHOLD = 0.50
DEFAULT_MIN_CLUSTER_SIZE = 2


def _article_texts(articles: list[dict]) -> list[str]:
    return [a.get("text", a.get("title", "")) for a in articles]


# Embeddings kept between pipeline runs in this process, by model, URL and
# text: an article stays in the feeds or the lookback window for many hourly
# runs and only needs embedding once. Trimmed to each run's articles.
_EMBEDDING_CACHE: dict = {}


class ArticleClusterer:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
        device: Optional[str] = None
    ):
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("sentence-transformers not installed. Clustering will use fallback mode.")
            self.model = None
        else:
            if device is None and TORCH_AVAILABLE:
                device = "cuda" if torch.cuda.is_available() else "cpu"
            elif device is None:
                device = "cpu"

            logger.info(f"Loading embedding model: {model_name} on {device}")
            self.model = SentenceTransformer(model_name, device=device)
            logger.info("Embedding model loaded")

    def _cache_keys(self, articles: list[dict], texts: list[str]) -> list[tuple]:
        return [(self.model_name, a.get("url") or "", hash(t)) for a, t in zip(articles, texts)]

    def embed_articles(self, articles: list[dict]) -> Optional[list]:
        if not self.model:
            logger.error("Embedding model not available")
            return None

        import numpy as np

        texts = _article_texts(articles)
        keys = self._cache_keys(articles, texts)
        missing = [i for i, k in enumerate(keys) if k not in _EMBEDDING_CACHE]
        if missing:
            logger.info(f"Embedding {len(missing)} articles ({len(keys) - len(missing)} already embedded)")
            new = self.model.encode([texts[i] for i in missing], show_progress_bar=True, convert_to_numpy=True)
            for i, vector in zip(missing, new):
                _EMBEDDING_CACHE[keys[i]] = vector
        embeddings = np.array([_EMBEDDING_CACHE[k] for k in keys])
        for stale in set(_EMBEDDING_CACHE) - set(keys):
            del _EMBEDDING_CACHE[stale]
        return embeddings

    def cached_embeddings(self, articles: list[dict]):
        """Embeddings for `articles`, reusing the ones this run's clustering
        made and embedding any others now. Unlike embed_articles, it leaves
        the cache alone: called with a subset, embed_articles would drop
        every other article's embedding before the next run."""
        import numpy as np

        texts = _article_texts(articles)
        keys = self._cache_keys(articles, texts)
        missing = [i for i, k in enumerate(keys) if k not in _EMBEDDING_CACHE]
        new = {}
        if missing:
            encoded = self.model.encode([texts[i] for i in missing], show_progress_bar=False, convert_to_numpy=True)
            new = dict(zip(missing, encoded))
        return np.array([new[i] if i in new else _EMBEDDING_CACHE[k] for i, k in enumerate(keys)])

    def compute_similarity_matrix(self, embeddings, texts: Optional[list[str]] = None):
        """Embedding similarity, blended with distinctive-word overlap when
        the articles' texts are given (see EMBEDDING_WEIGHT)."""
        if embeddings is None:
            return None

        from sklearn.metrics.pairwise import cosine_similarity
        similarity = cosine_similarity(embeddings)
        if texts:
            from sklearn.feature_extraction.text import TfidfVectorizer
            try:
                tfidf = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform(texts)
            except ValueError as e:  # no words left, e.g. all texts empty
                logger.warning(f"Word overlap unavailable, clustering on embeddings alone: {e}")
            else:
                similarity = EMBEDDING_WEIGHT * similarity + (1 - EMBEDDING_WEIGHT) * cosine_similarity(tfidf)
        return similarity

    def build_clusters(self, articles: list[dict], embeddings) -> list[list[int]]:
        if embeddings is None or len(embeddings) == 0 or len(articles) == 0:
            return [[i] for i in range(len(articles))]

        from sklearn.cluster import AgglomerativeClustering
        import numpy as np

        similarity_matrix = self.compute_similarity_matrix(embeddings, _article_texts(articles))

        if similarity_matrix is None:
            return [[i] for i in range(len(articles))]

        logger.debug(f"Similarity matrix:\n{np.round(similarity_matrix, 2)}")

        n_articles = len(articles)
        distance_matrix = 1 - similarity_matrix
        np.fill_diagonal(distance_matrix, 0)

        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - self.similarity_threshold,
            metric="precomputed",
            linkage="average"
        )

        labels = clustering.fit_predict(distance_matrix)

        clusters = {}
        for idx, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(idx)

        return list(clusters.values())

    def cluster(self, articles: list[dict]) -> dict[int, list[dict]]:
        return self.cluster_with_prior(articles, [])[0]

    def cluster_with_prior(self, articles: list[dict], prior: list[dict]) -> tuple[dict, dict]:
        """Group `articles` into topics, clustering them together with
        `prior` ones (earlier coverage, from the lookback window) so a story
        is recognized across days. Returns ({cluster_id: [articles]},
        {cluster_id: [prior articles on the same story]}).

        Only `articles` make up topics: a group needs min_cluster_size of
        them from at least 2 sources, else each becomes its own
        singleton_N (with the group's prior articles listed under that id).
        Prior articles only show who else has reported the story."""
        if not articles:
            logger.warning("No articles provided for clustering")
            return {}, {}

        everything = list(articles) + list(prior)
        logger.info(f"Clustering {len(articles)} articles with {len(prior)} from the lookback window")

        embeddings = self.embed_articles(everything)

        if embeddings is None:
            logger.warning("Embedding failed - returning articles as single clusters")
            return {i: [articles[i]] for i in range(len(articles))}, {}

        cluster_indices = self.build_clusters(everything, embeddings)

        result, prior_by_cluster = {}, {}
        singleton_count = 0
        for cluster_id, indices in enumerate(cluster_indices):
            cluster_articles = [everything[i] for i in indices if i < len(articles)]
            earlier = [everything[i] for i in indices if i >= len(articles)]
            if not cluster_articles:
                continue
            unique_sources = {a.get("source", "unknown") for a in cluster_articles}
            if len(cluster_articles) >= self.min_cluster_size and len(unique_sources) >= 2:
                ids = [cluster_id]
                result[cluster_id] = cluster_articles
            else:
                ids = [f"singleton_{singleton_count + i}" for i in range(len(cluster_articles))]
                singleton_count += len(cluster_articles)
                for key, article in zip(ids, cluster_articles):
                    result[key] = [article]
            if earlier:
                for key in ids:
                    prior_by_cluster[key] = earlier

        logger.info(f"Created {len(result)} clusters from {len(articles)} articles")
        return result, prior_by_cluster

    def cluster_with_metadata(self, articles: list[dict]) -> dict:
        clusters = self.cluster(articles)

        cluster_summaries = {}
        for cluster_id, cluster_articles in clusters.items():
            # sources/urls/titles are parallel lists — sources[i], urls[i], titles[i]
            # all describe the same article. DO NOT dedupe sources here; the
            # frontend relies on positional pairing to build clickable badges.
            sources = [a.get("source", "unknown") for a in cluster_articles]
            urls = [a.get("url", "") for a in cluster_articles]
            titles = [a.get("title", "Untitled") for a in cluster_articles]

            combined_text = " ".join(a.get("text", "") for a in cluster_articles)

            cluster_summaries[cluster_id] = {
                "articles": cluster_articles,
                "source_count": len(set(sources)),
                "sources": sources,
                "article_count": len(cluster_articles),
                "urls": urls,
                "titles": titles,
                "combined_text": combined_text[:5000]
            }

        return cluster_summaries


def cluster_articles(articles: list[dict], **kwargs) -> dict[int, list[dict]]:
    clusterer = ArticleClusterer(**kwargs)
    return clusterer.cluster(articles)


if __name__ == "__main__":
    test_articles = [
        {
            "title": "President Signs New Climate Bill",
            "text": "President Signs New Climate Bill Congress passed the landmark climate legislation on Tuesday, marking a historic shift in environmental policy.",
            "url": "https://example.com/climate-bill",
            "source": "CNN"
        },
        {
            "title": "Climate Legislation Update",
            "text": "The new climate bill passed Congress and was signed by the President. Environmental groups praised the historic legislation.",
            "url": "https://example.com/climate-legislation",
            "source": "NBC"
        },
        {
            "title": "Stock Market Hits Record High",
            "text": "The Dow Jones reached a new record high today as tech stocks continued their rally amid positive economic data.",
            "url": "https://example.com/stock-market",
            "source": "Reuters"
        },
        {
            "title": "Tech Stocks Rally Continues",
            "text": "Technology companies led the market higher today with major indices reaching all-time highs.",
            "url": "https://example.com/tech-rally",
            "source": "Bloomberg"
        },
        {
            "title": "Local Weather Forecast",
            "text": "Rain is expected tomorrow with temperatures in the mid-60s. Weather officials recommend carrying an umbrella.",
            "url": "https://example.com/weather",
            "source": "LocalNews"
        }
    ]

    print("\n=== Clustering Test ===")
    result = cluster_articles(test_articles)
    print(f"\nCreated {len(result)} clusters:\n")
    for cluster_id, articles in result.items():
        print(f"Cluster {cluster_id} ({len(articles)} articles):")
        for a in articles:
            print(f"  - [{a['source']}] {a['title']}")
        print()

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
DEFAULT_SIMILARITY_THRESHOLD = 0.40
DEFAULT_MIN_CLUSTER_SIZE = 2


class ArticleClusterer:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
        device: Optional[str] = None
    ):
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

    def embed_articles(self, articles: list[dict]) -> Optional[list]:
        if not self.model:
            logger.error("Embedding model not available")
            return None

        texts = [a.get("text", a.get("title", "")) for a in articles]
        embeddings = self.model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        return embeddings

    def compute_similarity_matrix(self, embeddings):
        if embeddings is None:
            return None

        from sklearn.metrics.pairwise import cosine_similarity
        return cosine_similarity(embeddings)

    def build_clusters(self, articles: list[dict], embeddings) -> list[list[int]]:
        if embeddings is None or len(embeddings) == 0 or len(articles) == 0:
            return [[i] for i in range(len(articles))]

        from sklearn.cluster import AgglomerativeClustering
        import numpy as np

        similarity_matrix = self.compute_similarity_matrix(embeddings)

        if similarity_matrix is None:
            return [[i] for i in range(len(articles))]

        import numpy as np
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
        if not articles:
            logger.warning("No articles provided for clustering")
            return {}

        logger.info(f"Clustering {len(articles)} articles")

        embeddings = self.embed_articles(articles)

        if embeddings is None:
            logger.warning("Embedding failed - returning articles as single clusters")
            return {i: [articles[i]] for i in range(len(articles))}

        cluster_indices = self.build_clusters(articles, embeddings)

        result = {}
        singleton_count = 0
        for cluster_id, indices in enumerate(cluster_indices):
            cluster_articles = [articles[i] for i in indices]
            if len(cluster_articles) >= self.min_cluster_size:
                result[cluster_id] = cluster_articles
            elif len(cluster_articles) == 1:
                result[f"singleton_{singleton_count}"] = cluster_articles
                singleton_count += 1

        logger.info(f"Created {len(result)} clusters from {len(articles)} articles")

        if not result:
            logger.warning("No clusters created - returning all as separate")
            return {i: [articles[i]] for i in range(len(articles))}

        return result

    def cluster_with_metadata(self, articles: list[dict]) -> dict:
        clusters = self.cluster(articles)

        cluster_summaries = {}
        for cluster_id, cluster_articles in clusters.items():
            sources = list(set(a.get("source", "unknown") for a in cluster_articles))
            urls = [a.get("url", "") for a in cluster_articles]
            titles = [a.get("title", "Untitled") for a in cluster_articles]

            combined_text = " ".join(a.get("text", "") for a in cluster_articles)

            cluster_summaries[cluster_id] = {
                "articles": cluster_articles,
                "source_count": len(sources),
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

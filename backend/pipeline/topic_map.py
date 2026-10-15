"""
backend/pipeline/topic_map.py

Where each topic sits on the Topics page's map. Political news is the
map's center, with health, tech and business as three points around it.
Each topic gets:

  - genre_weights: how much it belongs to each genre, summing to 1. The
    map places it at that blend of the four points, so a health policy
    story lands between politics and health.
  - neighbors: the topics whose articles read most like its own (by
    embedding), which the map draws close to it.

The frontend lays the circles out from these. Computed during the pipeline
run, while the clustering embeddings are still in memory; the web process
has no embedding model.
"""

import logging
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)

POLITICS = "politics"
GENRES = (POLITICS, "health", "tech", "business")

# Genre weights blend two signals: which feeds the topic's articles came
# from (exact, but all-or-nothing per article) and how close the articles
# read to each genre's articles overall (graded, so a political story about
# drug prices leans toward health). This is the feeds' share.
FEED_MIX_WEIGHT = 0.5
# A health, tech or business article about policy counts this much toward
# politics in the feed mix, and the rest toward its own genre.
POLICY_POLITICS_SHARE = 0.5
# Softmax temperature for embedding affinity. Affinities are cosines
# between mean-centered vectors, roughly -0.4 to 0.6; at 0.15 a 0.1 lead in
# cosine is a 1.9x lead in weight. Set on synthetic data, not live data:
# lower it if political topics drift toward the genres, raise it if policy
# topics sit too close to the center.
AFFINITY_TEMPERATURE = 0.15
# A genre needs this many articles in the run to get an embedding anchor.
# Without one, it's placed by the feed mix alone.
MIN_ANCHOR_ARTICLES = 3
# Nearest topics stored per topic, and the least similarity that counts.
MAP_NEIGHBORS = 6
MIN_NEIGHBOR_SIMILARITY = 0.2


def _unit(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=-1, keepdims=True)
    return m / np.maximum(norms, 1e-9)


def feed_genre(article: dict) -> str:
    """The genre of the feed an article came from. Articles saved before
    categories existed came from political feeds."""
    genre = article.get("category") or POLITICS
    return genre if genre in GENRES else POLITICS


def feed_mix(articles: list[dict], is_policy: Callable[[dict], bool]) -> np.ndarray:
    """Share of a topic's articles from each genre's feeds, with policy
    articles split between politics and their own genre."""
    mix = np.zeros(len(GENRES))
    for article in articles:
        g = GENRES.index(feed_genre(article))
        if g and is_policy(article):
            mix[0] += POLICY_POLITICS_SHARE
            mix[g] += 1 - POLICY_POLITICS_SHARE
        else:
            mix[g] += 1
    if not mix.sum():
        mix[0] = 1
    return mix / mix.sum()


def _softmax(scores: np.ndarray, temperature: float) -> np.ndarray:
    z = scores / temperature
    z = np.exp(z - z.max(axis=-1, keepdims=True))
    return z / z.sum(axis=-1, keepdims=True)


def build_topic_maps(
    topics: list[tuple[str, list[dict]]],
    reference: list[dict],
    embed: Callable[[list[dict]], np.ndarray],
    is_policy: Callable[[dict], bool],
) -> dict[str, dict]:
    """{cluster_id: {"genre_weights": {genre: weight}, "neighbors":
    [[cluster_id, similarity], ...]}}.

    `topics` pairs each topic's id with its articles (earlier coverage
    included). `reference` is every article clustered this run, which
    defines where each genre sits; topic articles are looked up in it, so
    they're only embedded again if missing. `embed` returns one vector per
    article."""
    if not topics:
        return {}

    vectors = _unit(np.asarray(embed(reference), dtype=float))
    row_of = {id(a): i for i, a in enumerate(reference)}

    # Each genre's anchor: the mean of its articles, measured from the
    # average of the genres (not of all articles, which political news
    # dominates). Centering is what makes the cosines discriminate: raw
    # news embeddings all sit fairly close together.
    genres = np.array([GENRES.index(feed_genre(a)) for a in reference])
    centroids = {
        g: vectors[genres == g].mean(axis=0)
        for g in range(len(GENRES))
        if (genres == g).sum() >= MIN_ANCHOR_ARTICLES
    }
    origin = np.mean(list(centroids.values()), axis=0) if len(centroids) >= 2 else np.zeros(vectors.shape[1])
    anchored = sorted(centroids) if len(centroids) >= 2 else []
    anchors = _unit(np.stack([centroids[g] - origin for g in anchored])) if anchored else None

    topic_vectors = []
    for _, articles in topics:
        missing = [a for a in articles if id(a) not in row_of]
        rows = [vectors[row_of[id(a)]] for a in articles if id(a) in row_of]
        if missing:
            rows.extend(_unit(np.asarray(embed(missing), dtype=float)))
        topic_vectors.append(np.mean(rows, axis=0) - origin)
    topic_vectors = _unit(np.stack(topic_vectors))

    weights = np.stack([feed_mix(articles, is_policy) for _, articles in topics])
    if anchors is not None:
        affinity = np.zeros_like(weights)
        affinity[:, anchored] = _softmax(topic_vectors @ anchors.T, AFFINITY_TEMPERATURE)
        weights = FEED_MIX_WEIGHT * weights + (1 - FEED_MIX_WEIGHT) * affinity
        weights /= weights.sum(axis=1, keepdims=True)

    similarity = topic_vectors @ topic_vectors.T
    np.fill_diagonal(similarity, -np.inf)
    ids = [str(cluster_id) for cluster_id, _ in topics]

    maps = {}
    for i, cluster_id in enumerate(ids):
        nearest = np.argsort(-similarity[i])[:MAP_NEIGHBORS]
        maps[cluster_id] = {
            "genre_weights": {g: round(float(w), 3) for g, w in zip(GENRES, weights[i])},
            "neighbors": [
                [ids[j], round(float(similarity[i, j]), 3)]
                for j in nearest
                if similarity[i, j] >= MIN_NEIGHBOR_SIMILARITY
            ],
        }
    logger.info(
        f"Topic map: {len(ids)} topics, anchors for {[GENRES[g] for g in anchored] or 'no genres'}"
    )
    return maps

"""
backend/pipeline/summarizer.py

Orchestrates the full Politerate pipeline:
1. Scrape articles from RSS feeds
2. Preprocess text
3. Cluster by topic
4. Filter by credibility
5. Summarize (when model is ready)
6. Highlight political terms

Usage:
    from backend.pipeline.summarizer import PoliteratePipeline
    pipeline = PoliteratePipeline()
    results = pipeline.run()
"""

import logging
import math
import re
from collections import Counter, defaultdict
from typing import Callable, Optional

from backend.pipeline.preprocessor import preprocess_batch
from backend.pipeline.clustering import cluster_articles, ArticleClusterer, DEFAULT_SIMILARITY_THRESHOLD
from backend.pipeline.credibility import filter_by_credibility
from backend.pipeline.highlighter import TermHighlighter
from backend.pipeline.topic_map import build_topic_maps
from backend.config import site_now
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# Regions, as tagged by rss_scraper (US / WORLD). Articles and clusters saved
# before regions existed count as U.S. news.
US_REGION = "us"
WORLD_REGION = "world"

# Tune from here. Topics compete for BRIEF_SLOTS spots in the Daily Brief by
# relevance: how many outlets reported them (counting earlier coverage in
# the lookback window), times a weight that favors U.S. political and policy
# news. A topic needs MIN_BRIEF_OUTLETS outlets to compete.
# MAX_CLUSTERS_IN_BRIEF_INPUT caps what we actually feed to the hierarchical
# BART pass — keeping the input short avoids degenerate generation when BART
# runs out of coherent things to say.
BRIEF_SLOTS = 10
MIN_BRIEF_OUTLETS = 3
BRIEF_WEIGHTS = {"us_politics": 1.5, "world_politics": 1.25, "genre": 1.0}
# Health, tech and business topics compete with each other for this many
# spots, and can take more by outscoring political ones.
GENRE_SLOTS = 2

# Categories, as tagged by rss_scraper. Articles saved before categories
# existed came from political feeds.
POLITICS = "politics"
# Health, tech and business topics go on to credibility analysis and
# summarizing only if they're political or about policy, or if this many
# outlets report them ("more than 3"; outlets, not articles, so one site's
# follow-ups don't count).
GENRE_MIN_OUTLETS = 4
# How far back earlier coverage counts toward a story's outlets, in hours.
# Outlets report the same story hours apart: over four days of articles the
# 4th outlet on a story came within 12 hours of the first 55% of the time,
# within 24h 77%, 36h 84%, 48h 90% (a recall picked up 28 hours late, say).
# Past ~36h it was mostly multi-day stories, which have fresh coverage each
# day anyway. Downloads older than this are deleted at the end of the day.
LOOKBACK_HOURS = 36
MAX_CLUSTERS_IN_BRIEF_INPUT = 5

# Conditional generation tiers: (source_token_threshold, (max_length, min_length)).
# Measured against the PRE-truncation token count, not BART's 1024-cap input.
#
# The fine-tuned model (summarizer.ipynb) was trained on targets truncated to
# 64 tokens, so it has never produced anything longer. Forcing a high
# min_length makes it keep generating after it wants to stop, and with
# no_repeat_ngram_size=3 blocking repeats it falls into junk tokens and
# merged words. Keep min_length low and max_length near the training length.
_SOURCE_BUDGET_TIERS = [
    (1200,           (64, 20)),   # ~1 short article
    (2800,           (80, 25)),   # ~2 articles
    (float("inf"),   (96, 30)),   # 3+ articles
]
# Extra max_length the retry gets to finish a sentence cut off at an
# abbreviation. min_length is NOT raised on retry, for the reason above.
_RETRY_EXTRA_TOKENS = 32

# Topic summaries are assembled from per-article summaries (see
# PoliteratePipeline.summarize_topic). BART truncates its input at 1024
# tokens, so summarizing a cluster's concatenated text only ever reflected
# its first article or two.
#
# Sentences per topic in the Daily Brief, and in the topic page's details.
BRIEF_MAX_SENTENCES = 5
DETAIL_MAX_SENTENCES = 10
# MMR trade-off between a sentence's relevance (how central it is across
# outlets) and its novelty relative to sentences already picked.
MMR_LAMBDA = 0.7
# Discourages taking a second sentence from an article that already
# contributed one, so a topic's summary spreads across its outlets.
ARTICLE_REPEAT_PENALTY = 0.15
# A sentence this similar to an already-picked one is dropped as a repeat.
# Sentence-embedding cosine and bag-of-words cosine sit on different
# scales, hence one threshold for each. Both were set on ~1,500 pairs of
# opening sentences from different outlets covering the same story: from
# 0.65 embedding similarity up, nearly every pair restates the same fact.
# Bag-of-words separates them less cleanly; at 0.35 it catches about 60% of
# those repeats and matches about 1% of pairs that say different things.
REDUNDANCY_THRESHOLD_EMBED = 0.65
REDUNDANCY_THRESHOLD_BOW = 0.35
# The topic overview is a second BART pass over the per-article summaries;
# stay under BART's 1024-token input window.
OVERVIEW_INPUT_TOKEN_BUDGET = 1000
# Same generation budget as the 3+ article tier: longer targets push the
# fine-tuned model past its training length (see _SOURCE_BUDGET_TIERS).
OVERVIEW_MAX_TOKENS = 96
OVERVIEW_MIN_TOKENS = 30
# Fallback relevance for articles with no credibility score.
DEFAULT_CREDIBILITY = 0.5
# Most new per-article summaries one pipeline run generates. The run shares
# the web server's CPU, and a backlog (first run after a deploy, or after
# downtime) would otherwise pin it for many minutes. Later runs pick up the
# rest; meanwhile topics are built from the summaries already stored.
MAX_NEW_ARTICLE_SUMMARIES_PER_RUN = 40


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


def _summary_bullets(summary: str) -> list[str]:
    """Split a cluster summary into one bullet per sentence for the Daily
    Brief. Bad sentences (garbled, fragments) are dropped individually so one
    broken sentence doesn't take the whole topic down with it."""
    if not summary or summary.startswith("["):
        return []
    bullets = []
    # BART sometimes emits newline-separated highlights (CNN/DailyMail style)
    # with no period between them, so split on lines before sentences.
    for line in _clean_bart_output(summary).splitlines():
        for sentence in _smart_sentence_split(line.strip()):
            sentence = sentence.strip()
            if len(sentence.split()) < MIN_SENT_WORDS or _looks_garbled(sentence):
                continue
            if sentence[-1] not in ".!?":
                sentence += "."
            bullets.append(sentence)
    return bullets


_STOPWORDS = frozenset("""
a about after again against all also an and any are as at be because been
before being between both but by can could did do does during each few for
from further had has have having he her here hers him his how if in into is
it its itself just more most my no nor not now of off on once only or other
our out over own said same say says she should so some such than that the
their them then there these they this those through to too under until up
very was we were what when where which while who whom why will with would
you your
""".split())
_WORD = re.compile(r"[a-z0-9]+")


def _stem(word: str) -> str:
    """Crude suffix folding so "voted"/"votes"/"vote" and "funding"/"funded"
    match. Good enough for comparing sentences about the same story."""
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and not word.endswith("ss") and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word


def _content_terms(text: str) -> list[str]:
    """Lowercased, stemmed content words, possessives dropped, so "the
    Senate's votes" and "the Senate voted" share terms."""
    text = re.sub(r"['’]s\b", "", text.lower())
    return [_stem(w) for w in _WORD.findall(text) if len(w) > 2 and w not in _STOPWORDS]


def _bow_similarity(texts_a: list[str], texts_b: list[str]) -> list[list[float]]:
    """Cosine similarity of term-count vectors."""
    def vectorize(texts):
        out = []
        for text in texts:
            counts = Counter(_content_terms(text))
            out.append((counts, math.sqrt(sum(v * v for v in counts.values()))))
        return out

    def cosine(a, b):
        (ca, na), (cb, nb) = a, b
        if not na or not nb:
            return 0.0
        if len(ca) > len(cb):
            ca, cb = cb, ca
        shared = [term for term in ca if term in cb]
        # One shared word (often just a name) doesn't make two sentences say
        # the same thing, but between short sentences it alone would score
        # past REDUNDANCY_THRESHOLD_BOW.
        if len(shared) < 2:
            return 0.0
        return sum(ca[term] * cb[term] for term in shared) / (na * nb)

    va, vb = vectorize(texts_a), vectorize(texts_b)
    return [[cosine(a, b) for b in vb] for a in va]


def _similarity(
    texts_a: list[str],
    texts_b: list[str],
    encode: Optional[Callable[[list[str]], object]] = None,
) -> tuple[list[list[float]], float]:
    """Cross-similarity matrix between two sentence lists, plus the
    redundancy threshold that fits its scale. Uses sentence embeddings when
    an encoder is available (it catches paraphrases), else bag-of-words."""
    if not texts_a or not texts_b:
        return [[0.0] * len(texts_b) for _ in texts_a], REDUNDANCY_THRESHOLD_BOW
    if encode is not None:
        try:
            import numpy as np
            emb = np.asarray(encode(list(texts_a) + list(texts_b)), dtype=float)
            emb = emb / np.clip(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9, None)
            a, b = emb[: len(texts_a)], emb[len(texts_a):]
            return (a @ b.T).tolist(), REDUNDANCY_THRESHOLD_EMBED
        except Exception as e:
            logger.warning(f"Sentence embedding failed, using bag-of-words similarity: {e}")
    return _bow_similarity(texts_a, texts_b), REDUNDANCY_THRESHOLD_BOW


def _rank_sentences(
    pool: list[dict],
    sim: list[list[float]],
    redundancy: float,
    limit: int,
    exclude: frozenset = frozenset(),
) -> list[int]:
    """Pick up to `limit` sentences from `pool` by maximal marginal relevance.

    Each pool item is {"text", "article", "source", "position", "credibility"},
    where `article` identifies the source article, `source` its outlet, and
    `position` is the sentence's index within that article's summary.
    Relevance is mostly cross-outlet support, so a fact several outlets
    report outranks one outlet's aside; position and source credibility
    break ties. Returns pool indices in pick order.
    """
    n = len(pool)
    if n == 0:
        return []

    # Support: for each other outlet, how far its closest sentence rises
    # above the topic's background similarity (75th percentile of
    # cross-outlet pairs), averaged over those outlets. Sentences that only
    # share the topic's vocabulary stay near the background and score ~0,
    # and text an outlet repeats across its own articles (page boilerplate,
    # a recycled paragraph) gains nothing from the repetition.
    outlet = [item.get("source", item["article"]) for item in pool]
    cross = sorted(sim[i][j] for i in range(n) for j in range(n) if outlet[i] != outlet[j])
    background = cross[int(0.75 * (len(cross) - 1))] if cross else 0.0
    sentences_of: dict = defaultdict(list)
    for j in range(n):
        sentences_of[outlet[j]].append(j)
    support = []
    for i in range(n):
        others = [o for o in sentences_of if o != outlet[i]]
        lift = sum(max(0.0, max(sim[i][j] for j in sentences_of[o]) - background) for o in others)
        support.append(lift / len(others) if others else 0.0)
    top = max(support) or 1.0
    relevance = [
        0.8 * support[i] / top
        + 0.1 / (1 + pool[i]["position"])
        + 0.1 * pool[i]["credibility"]
        for i in range(n)
    ]

    picked: list[int] = []
    used_articles: set = set()
    candidates = [i for i in range(n) if i not in exclude]
    while candidates and len(picked) < limit:
        best, best_score = None, None
        for i in list(candidates):
            overlap = max((sim[i][j] for j in picked), default=0.0)
            if overlap >= redundancy:
                candidates.remove(i)
                continue
            score = MMR_LAMBDA * relevance[i] - (1 - MMR_LAMBDA) * overlap
            if pool[i]["article"] in used_articles:
                score -= ARTICLE_REPEAT_PENALTY
            if best_score is None or score > best_score:
                best, best_score = i, score
        if best is None:
            break
        picked.append(best)
        candidates.remove(best)
        used_articles.add(pool[best]["article"])
    return picked


def _drop_redundant(candidates: list[str], shown: list[str]) -> list[str]:
    """`candidates` minus any sentence too similar to one in `shown` or to an
    earlier candidate. Runs in the web process (no embedding model loaded),
    so it uses the bag-of-words similarity."""
    if not candidates:
        return []
    texts = shown + candidates
    sim, redundancy = _similarity(texts, texts)
    kept_idx = list(range(len(shown)))
    kept = []
    for k in range(len(shown), len(texts)):
        if all(sim[k][j] < redundancy for j in kept_idx):
            kept_idx.append(k)
            kept.append(texts[k])
    return kept


def _credibility_score(article: dict) -> float:
    score = (article.get("credibility") or {}).get("score")
    return float(score) if score is not None else DEFAULT_CREDIBILITY


def cluster_region(cluster: dict) -> str:
    return cluster.get("region") or US_REGION


def majority_region(articles: list[dict]) -> str:
    """A topic's region: most of its articles' (ties go to U.S. news). Each
    article's own region comes from its outlet's URL section or feed, which
    can disagree between outlets on the same story (Al Jazeera's feed is all
    world news, for one). Articles from health, tech and business feeds only
    vote when no political feed covered the story: those sections aren't
    split by region, so their region is just the outlet's home (U.S. health
    desks covering the Pope's surgery, UK tech desks covering U.S. states
    suing OpenAI)."""
    voters = [a for a in articles if is_political(a)] or articles
    world = sum(1 for a in voters if a.get("region") == WORLD_REGION)
    return WORLD_REGION if world > len(voters) - world else US_REGION


def is_political(article: dict) -> bool:
    return (article.get("category") or POLITICS) == POLITICS


# Words in a headline that mark a health, tech or business story as being
# about government action. On ~240 hand-labelled health, tech and business
# headlines, these plus the feeds' policy sections found 84% of the policy
# stories and flagged 5 that weren't (a president's granddaughter in hospital,
# an "FDA-approved" treatment); most misses named UK ministers without a
# title. Topics are kept if any of their articles is flagged, which catches
# more of them.
_POLICY_WORDS = re.compile(r"\b(" + "|".join([
    r"congress\w*", r"senat\w*", r"lawmakers?", r"legislat\w*", r"white house", r"administration",
    r"trump\w*", r"biden", r"governor", r"mayor", r"minister", r"secretary", r"chancellor",
    r"parliament", r"westminster", r"government\w*", r"federal", r"fed", r"central bank",
    r"bank of england", r"treasury", r"irs", r"fda", r"ftc", r"fcc", r"cdc", r"hhs", r"epa", r"doj",
    r"justice department", r"supreme court", r"attorney general", r"states? (?:sue|sues|sued|accuse)\w*",
    r"sued by \d+ states", r"regulat\w*", r"fined?", r"fines", r"sanctions?", r"tariffs?", r"tax(?:es)?",
    r"subsid\w*", r"bans?", r"policy", r"policies", r"budget", r"elections?", r"midterms?", r"voters?",
    r"medicare", r"medicaid", r"social security", r"cola", r"obamacare", r"affordable care act", r"nhs",
    r"minimum wage", r"aid", r"pac", r"lobby\w*", r"imf", r"authorities", r"crackdown",
]) + r")\b", re.IGNORECASE)


def mentions_policy(headline: str) -> bool:
    return bool(_POLICY_WORDS.search(headline or ""))


def is_policy_article(article: dict) -> bool:
    """A health, tech or business article about government action."""
    return bool(article.get("policy")) or mentions_policy(article.get("title", ""))


def topic_is_political(articles: list[dict]) -> bool:
    """Political news, or health, tech or business news about policy, which
    counts the same as political news."""
    return any(is_political(a) or is_policy_article(a) for a in articles)


def topic_category(articles: list[dict]) -> str:
    """POLITICS for political and policy topics, else the most common of
    the articles' categories."""
    if topic_is_political(articles):
        return POLITICS
    return Counter(a.get("category") for a in articles).most_common(1)[0][0]


def story_outlets(articles: list[dict], prior: list[dict] = ()) -> int:
    """Outlets that reported a story: today's articles' plus earlier
    coverage from the lookback window."""
    return len({a.get("source") for a in list(articles) + list(prior)})


def gate_genre_topics(clusters: dict, prior_by_cluster: Optional[dict] = None) -> tuple[dict, list[dict]]:
    """(kept topics, dropped articles). Political and policy topics are
    kept, and so are health, tech and business topics at least
    GENRE_MIN_OUTLETS outlets have reported, counting earlier coverage in
    the lookback window (which also counts toward "political"). Dropped
    articles have only been embedded and compared with the rest; they stay
    in the download cache, so each hourly run re-checks them as more
    outlets report, until the end-of-day prune deletes them."""
    prior_by_cluster = prior_by_cluster or {}
    kept, dropped = {}, []
    for cluster_id, articles in clusters.items():
        prior = prior_by_cluster.get(cluster_id, [])
        if topic_is_political(articles + prior) or story_outlets(articles, prior) >= GENRE_MIN_OUTLETS:
            kept[cluster_id] = articles
        else:
            dropped.extend(articles)
    return kept, dropped


def cluster_outlets(cluster: dict) -> int:
    """Outlets that reported a saved topic. Topics saved before outlet
    counts were stored list each outlet once in `sources`."""
    return cluster.get("outlet_count") or len(set(cluster.get("sources") or []))


def is_genre_topic(cluster: dict) -> bool:
    return (cluster.get("category") or POLITICS) != POLITICS


def brief_relevance(cluster: dict) -> float:
    """Outlets reporting the topic, weighted toward U.S. political and
    policy news (BRIEF_WEIGHTS)."""
    if is_genre_topic(cluster):
        weight = BRIEF_WEIGHTS["genre"]
    elif cluster_region(cluster) == US_REGION:
        weight = BRIEF_WEIGHTS["us_politics"]
    else:
        weight = BRIEF_WEIGHTS["world_politics"]
    return cluster_outlets(cluster) * weight


def is_brief_topic(cluster: dict) -> bool:
    """A real multi-article topic enough outlets have reported to compete
    for the Daily Brief."""
    return (
        not str(cluster.get("cluster_id", "")).startswith("singleton_")
        and cluster_outlets(cluster) >= MIN_BRIEF_OUTLETS
    )


def select_brief_clusters(clusters: list[dict]) -> list[dict]:
    """The Daily Brief's topics, most relevant first: the best GENRE_SLOTS
    health, tech and business topics, then whatever topics of any kind are
    most relevant (brief_relevance), up to BRIEF_SLOTS in all."""
    eligible = sorted((c for c in clusters if is_brief_topic(c)), key=brief_relevance, reverse=True)
    selected = [c for c in eligible if is_genre_topic(c)][:GENRE_SLOTS]
    chosen = {id(c) for c in selected}
    for c in eligible:
        if len(selected) >= BRIEF_SLOTS:
            break
        if id(c) not in chosen:
            selected.append(c)
            chosen.add(id(c))
    return sorted(selected, key=brief_relevance, reverse=True)


class PoliteratePipeline:
    def __init__(
        self,
        model_path: Optional[str] = None,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
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
        # Remaining new article summaries allowed this run; None = no limit
        # (process_clusters sets it for scheduled runs).
        self._summary_budget: Optional[int] = None

    def scrape(self) -> dict:
        logger.info("Step 1: Scraping articles...")
        try:
            from backend.pipeline.rss_scraper import get_all_top_story_links
            from backend.pipeline.scraper import scrape_articles_by_source
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
        return self.cluster_with_prior(articles, [])[0]

    def cluster_with_prior(self, articles: list[dict], prior: list[dict]) -> tuple[dict, dict]:
        """({cluster_id: [articles]}, {cluster_id: [prior articles on the
        same story]}); see ArticleClusterer.cluster_with_prior."""
        logger.info("Step 3: Clustering articles by topic...")
        self.clusterer = ArticleClusterer(
            similarity_threshold=self.similarity_threshold,
            min_cluster_size=self.min_cluster_size
        )
        clusters, prior_by_cluster = self.clusterer.cluster_with_prior(articles, prior)
        logger.info(f"Created {len(clusters)} topic clusters")
        return clusters, prior_by_cluster

    def filter_credibility(self, articles: list[dict]) -> tuple[list[dict], list[dict]]:
        logger.info("Step 4: Filtering by credibility...")
        try:
            from backend.db.cache import get_cached_analyses
            cached = get_cached_analyses([a["url"] for a in articles if a.get("url")])
        except Exception as e:
            logger.warning(f"Could not load stored analyses, analyzing everything: {e}")
            cached = {}
        passed, failed = filter_by_credibility(articles, cached)
        logger.info(f"Credibility filter: {len(passed)} passed, {len(failed)} filtered")
        return passed, failed

    def _lookback_articles(self, exclude_urls) -> list[dict]:
        try:
            from backend.db.cache import get_lookback_articles
            return get_lookback_articles(LOOKBACK_HOURS, exclude_urls)
        except Exception as e:
            logger.warning(f"Could not load earlier coverage, counting today's outlets only: {e}")
            return []

    def _check_genre_credibility(self, clusters: dict) -> tuple[dict, list[dict]]:
        """Credibility-check the health, tech and business articles in the
        kept topics, as political articles were before clustering. Returns
        the topics without the ones that failed (a topic left with too few
        articles or outlets splits into single articles) and those failures."""
        genre = [a for articles in clusters.values() for a in articles if not is_political(a)]
        if not genre:
            return clusters, []
        _, failed = self.filter_credibility(genre)
        failed_ids = {id(a) for a in failed}
        checked = {}
        for cluster_id, articles in clusters.items():
            kept = [a for a in articles if id(a) not in failed_ids]
            is_topic = not str(cluster_id).startswith("singleton_")
            if len(kept) == len(articles) or (
                is_topic
                and len(kept) >= self.min_cluster_size
                and len({a.get("source") for a in kept}) >= 2
            ):
                checked[cluster_id] = kept
            else:
                for i, article in enumerate(kept):
                    checked[f"singleton_{cluster_id}_{i}"] = [article]
        return checked, failed

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
          3. If still garbled OR truncated at an abbreviation, ONE retry with
             a little more max_length room (same min_length) so BART can
             finish the sentence without being forced past its stopping point.
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

        logger.warning(
            "Retry (tokens=%d, garbled=%s, truncated=%s)",
            source_tokens, is_garbled, is_truncated,
        )

        retry = _clean_bart_output(self._bart_generate(
            text,
            max_length=effective_max + _RETRY_EXTRA_TOKENS,
            min_length=effective_min,
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
        return select_brief_clusters(clusters)

    def _sentence_encoder(self) -> Optional[Callable[[list[str]], object]]:
        """Reuse the clustering embedding model (already loaded for this
        run) to compare summary sentences."""
        model = getattr(self.clusterer, "model", None)
        if model is None:
            return None
        return lambda texts: model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

    def _article_summary(self, article: dict) -> str:
        """The article's own BART summary: cached from an earlier run, else
        generated now (within this run's budget) and saved immediately, so an
        interrupted run keeps the summaries it already paid for."""
        cached = (article.get("summary") or "").strip()
        if cached and not cached.startswith("["):
            return cached
        if not self._model or not article.get("text"):
            return ""
        if self._summary_budget is not None:
            if self._summary_budget <= 0:
                return ""
            self._summary_budget -= 1
        summary = self.summarize(article["text"])
        if not summary or summary.startswith("["):
            return ""
        article["summary"] = summary
        article["summarized_at"] = site_now().isoformat()
        try:
            from backend.db.cache import save_article_summary
            save_article_summary(article)
        except Exception as e:
            logger.warning(f"Could not save summary for {article.get('url')}: {e}")
        return summary

    def _topic_overview(self, pool: list[dict], sim: list[list[float]]) -> str:
        """Second BART pass over the per-article summaries, which (unlike the
        full articles) fit inside BART's input window together.

        Summaries go in most-representative-first, so BART's lead bias favors
        the account the outlets agree on. Returns "" when the model is
        missing or the output is unusable; the caller falls back to
        extracted sentences.
        """
        if not self._model:
            return ""
        by_article: dict = defaultdict(list)
        for i, item in enumerate(pool):
            by_article[item["article"]].append(i)
        if len(by_article) < 2:
            return ""

        def centrality(article_idx) -> float:
            mine = by_article[article_idx]
            others = [j for j, item in enumerate(pool) if item["article"] != article_idx]
            return sum(sim[i][j] for i in mine for j in others) / (len(mine) * len(others))

        parts, used = [], 0
        for article_idx in sorted(by_article, key=centrality, reverse=True):
            text = " ".join(pool[i]["text"] for i in by_article[article_idx])
            tokens = self._source_token_count(text) or len(text.split()) * 2
            if parts and used + tokens > OVERVIEW_INPUT_TOKEN_BUDGET:
                break
            parts.append(text)
            used += tokens

        overview = self.summarize(
            " ".join(parts),
            max_length=OVERVIEW_MAX_TOKENS,
            min_length=OVERVIEW_MIN_TOKENS,
        )
        if (not overview or overview.startswith("[") or _looks_garbled(overview)
                or len(overview.split()) < 2 * MIN_SENT_WORDS):
            return ""
        return overview

    def summarize_topic(self, articles: list[dict]) -> dict:
        """Build a cluster's summaries from its articles' own summaries.

        Returns {"summary", "detailed_summary"}:
          - summary: the Daily Brief text. The most central, non-redundant
            sentences across all the articles, spread over different
            outlets; one bullet per sentence.
          - detailed_summary: the topic page's in-depth version,
            {"overview": str, "details": [{"text", "source", "url",
            "also_reported_by"}]}. The overview is a fused BART summary of
            every article's summary; the details are a longer set of distinct
            facts not already in the overview, each attributed to the outlet
            that reported it (and any others that repeated it).
        """
        pool = []
        for idx, article in enumerate(articles):
            credibility = _credibility_score(article)
            for position, sentence in enumerate(_summary_bullets(self._article_summary(article))):
                pool.append({
                    "text": sentence,
                    "article": idx,
                    "source": article.get("source", idx),
                    "position": position,
                    "credibility": credibility,
                })

        if not pool:
            # No usable per-article summaries (model not loaded, or every
            # output was garbled): one pass over the concatenated text.
            text = " ".join(a.get("text", "") for a in articles)
            return {"summary": self.summarize(text), "detailed_summary": None}

        encode = self._sentence_encoder()
        texts = [item["text"] for item in pool]
        sim, redundancy = _similarity(texts, texts, encode)

        brief = _rank_sentences(pool, sim, redundancy, BRIEF_MAX_SENTENCES)

        overview = self._topic_overview(pool, sim)
        overview_sentences = _summary_bullets(overview) if overview else []
        if overview_sentences:
            cross, cross_redundancy = _similarity(overview_sentences, texts, encode)
            covered = {j for row in cross for j, s in enumerate(row) if s >= cross_redundancy}
        else:
            lead = brief[:3]
            overview = " ".join(texts[i] for i in lead)
            covered = {j for i in lead for j in range(len(pool)) if sim[i][j] >= redundancy}
            covered.update(lead)

        details = _rank_sentences(
            pool, sim, redundancy, DETAIL_MAX_SENTENCES, exclude=frozenset(covered)
        )

        def detail(i: int) -> dict:
            article = articles[pool[i]["article"]]
            # Other outlets with a sentence that repeats this fact.
            also = []
            for j, item in enumerate(pool):
                source = articles[item["article"]].get("source", "unknown")
                if (item["article"] != pool[i]["article"] and sim[i][j] >= redundancy
                        and source != article.get("source") and source not in also):
                    also.append(source)
            return {
                "text": texts[i],
                "source": article.get("source", "unknown"),
                "url": article.get("url", ""),
                "also_reported_by": also,
            }

        return {
            "summary": " ".join(texts[i] for i in brief),
            "detailed_summary": {
                "overview": overview,
                "details": [detail(i) for i in details],
            },
        }

    def _attach_cached_summaries(self, clusters: dict) -> None:
        """Reuse per-article summaries from earlier runs. Articles stay in the
        RSS feeds for hours, so without this every hourly run would
        re-summarize all of them."""
        articles = [
            a for cluster_id, arts in clusters.items()
            if not str(cluster_id).startswith("singleton_")
            for a in arts if a.get("url") and not a.get("summary")
        ]
        if not articles:
            return
        try:
            from backend.db.cache import get_article_summaries
            cached = get_article_summaries([a["url"] for a in articles])
        except Exception as e:
            logger.warning(f"Could not load cached article summaries: {e}")
            return
        for a in articles:
            if a["url"] in cached:
                a["summary"], a["summarized_at"] = cached[a["url"]]
        logger.info(f"Reusing cached summaries for {len(cached)}/{len(articles)} clustered articles")

    def create_daily_summary(self, clusters: list[dict]) -> str:
        """Build a coherent daily brief via hierarchical summarization.

        Strategy:
          1. Take the brief's topics (is_brief_topic), the caller's order.
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

    def build_daily_brief(self, clusters: list[dict]) -> dict:
        """The bulleted Daily Brief for a set of clusters (today's, or an
        archived day's) plus its stats, without the unified summary."""
        data = self.get_daily_summary_data(clusters, include_unified=False)
        return {
            key: data[key]
            for key in ("sections", "cluster_count", "source_count", "source_links", "total_articles")
        }

    def get_daily_summary_data(self, clusters: list[dict], include_unified: bool = True) -> dict:
        """Get all data needed for the daily summary view."""
        filtered_clusters = [c for c in clusters if is_brief_topic(c)]
        filtered_clusters.sort(key=brief_relevance, reverse=True)

        # Collect unique sources across all clusters. One representative URL
        # per source (the first one we saw for that source) so badges can
        # link somewhere even at the daily-brief level.
        source_to_url: dict[str, str] = {}
        all_article_count = 0
        for cluster in filtered_clusters:
            sources = cluster.get("sources", [])
            urls = cluster.get("urls", [])
            for i, src in enumerate(sources):
                if src and src not in source_to_url:
                    source_to_url[src] = urls[i] if i < len(urls) else ""
            all_article_count += cluster.get("article_count", 0)

        unique_sources = sorted(source_to_url.keys())
        source_links = [{"source": s, "url": source_to_url[s]} for s in unique_sources]

        # Bulleted brief: one section per top topic, one bullet per sentence.
        # Each bullet is highlighted separately so term markup never spans two.
        # Every bullet is checked against all bullets shown before it, across
        # topics: each topic's own bullets were picked to be distinct, but two
        # topics can cover the same story, and summaries saved before that
        # selection existed can repeat themselves. A topic left with no new
        # bullets duplicates an earlier one and is left out.
        sections = []
        shown: list[str] = []
        for c in self._select_brief_clusters(clusters):
            bullets = _drop_redundant(_summary_bullets(c.get("summary", "")), shown)
            if not bullets:
                continue
            shown.extend(bullets)
            sections.append({
                "cluster_id": c.get("cluster_id"),
                "headline": (c.get("titles") or [""])[0],
                "bullets": [self.highlighter.highlight(b) for b in bullets],
                "article_count": c.get("article_count", 0),
                "region": cluster_region(c),
                # For sizing topics: outlets reporting the story, and its
                # weighted relevance (brief_relevance), highest first.
                "outlet_count": cluster_outlets(c),
                "category": c.get("category") or POLITICS,
                "relevance": brief_relevance(c),
                # For tagging policy topics with their genre too; missing on
                # topics saved before the map existed.
                "genre_weights": (c.get("map") or {}).get("genre_weights"),
            })

        unified_summary = self.create_daily_summary(filtered_clusters) if include_unified else ""
        return {
            "sections": sections,
            "unified_summary": unified_summary,
            "highlighted_summary": self.highlighter.highlight(unified_summary),
            "cluster_count": len(filtered_clusters),
            "source_count": len(unique_sources),
            "sources": unique_sources,
            "source_links": source_links,
            "total_articles": all_article_count,
            "clusters": filtered_clusters
        }

    def process_clusters(self, clusters: dict, prior_by_cluster: Optional[dict] = None) -> list[dict]:
        """Summarize each topic. `prior_by_cluster` (earlier coverage in the
        lookback window) counts toward a topic's outlets and category only;
        summaries use today's articles."""
        prior_by_cluster = prior_by_cluster or {}
        results = []
        self._attach_cached_summaries(clusters)
        self._summary_budget = MAX_NEW_ARTICLE_SUMMARIES_PER_RUN

        for cluster_id, articles in clusters.items():
            if str(cluster_id).startswith("singleton_"):
                continue
            if len(articles) < 2:
                continue

            # Build source→URL map in insertion order so sources[i] and urls[i]
            # are always the same article (frontend pairs them by index).
            seen_sources: dict[str, str] = {}
            for a in articles:
                src = a.get("source", "unknown")
                if src not in seen_sources:
                    seen_sources[src] = a.get("url", "")
            sources = list(seen_sources.keys())
            source_urls = list(seen_sources.values())

            # One region per story: every article takes its topic's, so the
            # same story isn't tagged U.S. on one card and World on another.
            region = majority_region(articles)
            for a in articles:
                a["region"] = region

            results.append({
                "cluster_id": cluster_id,
                "article_count": len(articles),
                "region": region,
                "category": topic_category(articles + prior_by_cluster.get(cluster_id, [])),
                "outlet_count": story_outlets(articles, prior_by_cluster.get(cluster_id, [])),
                "sources": sources,
                "urls": source_urls,
                "titles": [a.get("title") for a in articles],
                **self.build_cluster_summaries(articles),
                "articles": articles
            })

        return results

    def attach_topic_maps(self, results: list[dict], prior_by_cluster: dict, reference: list[dict]) -> None:
        """Each topic's place on the Topics page's map (topic_map), from
        this run's clustering embeddings. `reference` is every article
        clustered this run. Topics keep no map data if embedding is
        unavailable; the map then places them by category alone."""
        model = getattr(self.clusterer, "model", None)
        if not results or model is None:
            return
        try:
            maps = build_topic_maps(
                [(r["cluster_id"], r["articles"] + prior_by_cluster.get(r["cluster_id"], [])) for r in results],
                reference,
                self.clusterer.cached_embeddings,
                is_policy_article,
            )
        except Exception as e:
            logger.warning(f"Topic map data unavailable this run: {e}")
            return
        for r in results:
            r["map"] = maps.get(str(r["cluster_id"]))

    def build_cluster_summaries(self, articles: list[dict]) -> dict:
        """summarize_topic plus glossary highlighting and the key terms."""
        topic = self.summarize_topic(articles)
        summary = topic["summary"]
        detailed = topic["detailed_summary"]

        term_text = [summary]
        if detailed:
            detailed["overview_html"] = self.highlight_terms(detailed["overview"])
            for detail in detailed["details"]:
                detail["html"] = self.highlight_terms(detail["text"])
            term_text.append(detailed["overview"])
            term_text.extend(d["text"] for d in detailed["details"])

        return {
            "summary": summary,
            "highlighted_summary": self.highlight_terms(summary),
            "detailed_summary": detailed,
            "defined_terms": self.highlighter.get_term_definitions(" ".join(term_text)),
        }

    def _build_raw_articles_with_dedup(self) -> dict:
        """Fetch RSS links, download only new URLs, merge with archive. Returns
        {source: {url: article}}; each article carries its feed's region,
        category and policy flag (rss_scraper.get_feed_links)."""
        try:
            from backend.pipeline.rss_scraper import get_feed_links
            from backend.pipeline.scraper import scrape_articles_by_source
        except ImportError as e:
            logger.error(f"Import error: {e}")
            return {}

        from backend.db.cache import (
            filter_unseen_urls,
            mark_urls_seen,
            archive_articles,
            get_archived_articles,
        )

        # Old downloads are pruned at the end of each day (main.daily_snapshot_job).
        links_by_source, meta_by_url = get_feed_links()
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
                    # Stored with the download, for when the article is
                    # earlier coverage in a later day's lookback.
                    article.update(meta_by_url.get(url, {}))
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
                    meta = meta_by_url.get(url, {})
                    art["region"] = meta.get("region", US_REGION)
                    art["category"] = meta.get("category", POLITICS)
                    art["policy"] = meta.get("policy", False)
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

        # Flatten {source: {url: article}} into a list, deduping by URL.
        # RSS feeds overlap (e.g. NYPost Politics and NYPost US News both
        # list the same article), so the same URL can appear under two
        # different source labels. Without this guard those identical
        # articles cluster together and render as duplicate badges.
        flat_articles = []
        seen_urls = set()
        skipped_dupes = 0
        for source, articles in raw_articles.items():
            for url, article in articles.items():
                if url in seen_urls:
                    skipped_dupes += 1
                    continue
                seen_urls.add(url)
                article["source"] = source
                flat_articles.append(article)
        if skipped_dupes:
            logger.info(
                f"Deduped {skipped_dupes} cross-feed duplicate URL(s) "
                f"during pipeline flatten"
            )

        if not flat_articles:
            logger.warning("No articles to process")
            return {"clusters": [], "stats": {"total": 0}}

        processed = self.preprocess(flat_articles)
        political = [a for a in processed if is_political(a)]
        genre = [a for a in processed if not is_political(a)]
        # Earlier coverage: articles first downloaded within the lookback
        # window that today's feeds no longer list. They're clustered with
        # today's articles only to count who else reported each story.
        prior = self.preprocess(self._lookback_articles(seen_urls))

        # Political news is credibility-checked before clustering. Health,
        # tech and business articles are clustered unchecked, and only the
        # ones in topics worth keeping get checked afterwards, so the rest
        # cost no more than their embedding.
        passed, failed = self.filter_credibility(political)

        clusters, prior_by_cluster = self.cluster_with_prior(passed + genre, prior)
        clusters, dropped = gate_genre_topics(clusters, prior_by_cluster)
        clusters, genre_failed = self._check_genre_credibility(clusters)
        failed += genre_failed
        logger.info(
            f"Health/tech/business: {len(genre)} articles, {len(dropped)} dropped "
            f"(not political, not policy, fewer than {GENRE_MIN_OUTLETS} outlets), "
            f"{len(genre_failed)} failed credibility"
        )

        results = self.process_clusters(clusters, prior_by_cluster)
        self.attach_topic_maps(results, prior_by_cluster, passed + genre + prior)

        # Persist every article that didn't make it into a named cluster so
        # the articles table holds the full picture, not just clustered ones.
        from backend.db.cache import save_unclustered_articles

        singleton_articles = []
        for cluster_id, arts in clusters.items():
            if str(cluster_id).startswith("singleton_"):
                for art in arts:
                    art["cluster_id"] = str(cluster_id)
                singleton_articles.extend(arts)

        save_unclustered_articles(singleton_articles)
        save_unclustered_articles(failed)

        stats = {
            "total_scraped": len(flat_articles),
            "total_processed": len(processed),
            "genre_articles": len(genre),
            "genre_dropped": len(dropped),
            "lookback_articles": len(prior),
            "passed_credibility": len(passed),
            "filtered_credibility": len(failed),
            "singleton_articles": len(singleton_articles),
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

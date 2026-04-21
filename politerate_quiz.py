"""
politerate_quiz.py

Rule-based quiz and term-of-the-day generator for the Politerate learning tool.
Pulls from the glossary in politerate.py and prioritizes terms that appear in
today's scraped articles so questions stay grounded in current events.
"""

import random
import re
from typing import Optional

from politerate import TermHighlighter


SNIPPET_CHARS = 220


def _snippet_for_term(text: str, term: str) -> Optional[str]:
    if not text or not term:
        return None
    pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None

    start = max(0, match.start() - SNIPPET_CHARS // 2)
    end = min(len(text), match.end() + SNIPPET_CHARS // 2)
    snippet = text[start:end].strip()

    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"

    return snippet


def _article_snippets_for_term(articles: list[dict], term: str, limit: int = 3) -> list[dict]:
    hits = []
    seen_urls = set()
    for article in articles:
        if article.get("url") in seen_urls:
            continue
        snippet = _snippet_for_term(article.get("text", ""), term)
        if snippet:
            hits.append({
                "source": article.get("source", "Unknown"),
                "url": article.get("url", "#"),
                "title": article.get("title", ""),
                "snippet": snippet,
            })
            seen_urls.add(article.get("url"))
            if len(hits) >= limit:
                break
    return hits


def _terms_appearing_in_articles(articles: list[dict], highlighter: TermHighlighter) -> list[str]:
    found = highlighter.find_terms_with_sources(articles)
    return [t for t, sources in found.items() if sources]


def pick_term_of_day(articles: list[dict], rng: Optional[random.Random] = None) -> dict:
    """Pick a political term to feature today.

    Prefers terms found in today's articles so the learner sees the concept
    applied to current news. Falls back to a random glossary term otherwise.
    """
    highlighter = TermHighlighter()
    glossary = highlighter.glossary
    rng = rng or random.Random()

    in_news = _terms_appearing_in_articles(articles, highlighter)
    pool = in_news if in_news else list(glossary.keys())
    if not pool:
        return {}

    term = rng.choice(pool)
    info = glossary.get(term, {})

    return {
        "term": term,
        "definition": info.get("definition", ""),
        "category": info.get("category", ""),
        "in_news": term in in_news,
        "article_snippets": _article_snippets_for_term(articles, term, limit=3),
    }


def _build_distractors(
    correct_term: str,
    glossary: dict,
    rng: random.Random,
    k: int = 3
) -> list[str]:
    correct_category = glossary.get(correct_term, {}).get("category", "")
    same_cat = [
        t for t, info in glossary.items()
        if t != correct_term and info.get("category") == correct_category
    ]
    other = [t for t in glossary if t != correct_term and t not in same_cat]

    distractors: list[str] = []
    rng.shuffle(same_cat)
    distractors.extend(same_cat[:k])

    if len(distractors) < k:
        rng.shuffle(other)
        distractors.extend(other[: k - len(distractors)])

    return distractors[:k]


def _build_definition_question(
    term: str,
    glossary: dict,
    articles: list[dict],
    rng: random.Random
) -> dict:
    info = glossary[term]
    distractors = _build_distractors(term, glossary, rng, k=3)

    correct_option = {"text": info.get("definition", ""), "correct": True}
    wrong_options = [
        {"text": glossary[d].get("definition", ""), "correct": False}
        for d in distractors
    ]
    options = [correct_option] + wrong_options
    rng.shuffle(options)

    return {
        "type": "definition",
        "prompt": f"Which of these best defines \"{term}\"?",
        "term": term,
        "category": info.get("category", ""),
        "options": options,
        "article_snippet": (_article_snippets_for_term(articles, term, limit=1) or [None])[0],
        "explanation": info.get("definition", ""),
    }


def _build_term_question(
    term: str,
    glossary: dict,
    articles: list[dict],
    rng: random.Random
) -> dict:
    info = glossary[term]
    distractors = _build_distractors(term, glossary, rng, k=3)

    options = [{"text": term, "correct": True}] + [
        {"text": d, "correct": False} for d in distractors
    ]
    rng.shuffle(options)

    return {
        "type": "term",
        "prompt": f"Which political term matches this definition?\n\n\"{info.get('definition', '')}\"",
        "term": term,
        "category": info.get("category", ""),
        "options": options,
        "article_snippet": (_article_snippets_for_term(articles, term, limit=1) or [None])[0],
        "explanation": f"{term}: {info.get('definition', '')}",
    }


def _build_headline_question(
    term: str,
    articles: list[dict],
    glossary: dict,
    rng: random.Random,
) -> Optional[dict]:
    """Show a real article headline + sentence-level context, ask which term fits.

    Unlike fill-in-the-blank on raw news text, this preserves full context so
    the reader has enough to identify the concept. Distractors deliberately
    exclude any term that ALSO appears in the article body, to avoid ambiguity.
    """
    candidates = []
    for article in articles:
        text = article.get("text", "") or ""
        if not _has_term(text, term):
            continue
        title = article.get("title") or ""
        if not title:
            continue
        sentence = _sentence_containing_term(text, term)
        candidates.append({
            "source": article.get("source", "Unknown"),
            "url": article.get("url", "#"),
            "title": title,
            "sentence": sentence,
            "text": text,
        })

    if not candidates:
        return None

    choice = rng.choice(candidates)

    terms_in_article = {
        t for t in glossary if _has_term(choice["text"], t)
    }
    distractor_pool = [
        t for t in glossary
        if t != term and t not in terms_in_article
    ]
    rng.shuffle(distractor_pool)

    correct_cat = glossary.get(term, {}).get("category", "")
    same_cat = [t for t in distractor_pool if glossary.get(t, {}).get("category") == correct_cat]
    other_cat = [t for t in distractor_pool if glossary.get(t, {}).get("category") != correct_cat]
    distractors = (same_cat[:2] + other_cat)[:3]

    if len(distractors) < 3:
        return None

    options = [{"text": term, "correct": True}] + [
        {"text": d, "correct": False} for d in distractors
    ]
    rng.shuffle(options)

    context_line = choice["sentence"] or choice["title"]

    return {
        "type": "headline",
        "prompt": (
            f"Which political term is central to this news story?\n\n"
            f"Headline: \"{choice['title']}\"\n\n"
            f"Context: \"{context_line}\""
        ),
        "term": term,
        "category": glossary.get(term, {}).get("category", ""),
        "options": options,
        "article_snippet": {
            "source": choice["source"],
            "url": choice["url"],
            "title": choice["title"],
            "snippet": context_line,
        },
        "explanation": f"{term}: {glossary.get(term, {}).get('definition', '')}",
    }


def _has_term(text: str, term: str) -> bool:
    return bool(re.search(r"\b" + re.escape(term) + r"\b", text or "", re.IGNORECASE))


def _sentence_containing_term(text: str, term: str) -> str:
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
    for s in sentences:
        if pattern.search(s):
            return s.strip()
    return ""


def build_quiz(
    articles: list[dict],
    count: int = 5,
    rng: Optional[random.Random] = None
) -> dict:
    """Generate a rule-based quiz of `count` multiple-choice questions.

    Strategy:
      - Prefer terms that appear in today's articles (lets us ground in news).
      - Mix three question types: definition→term, term→definition, and
        fill-in-the-blank using real article snippets.
    """
    highlighter = TermHighlighter()
    glossary = highlighter.glossary
    rng = rng or random.Random()

    if not glossary:
        return {"questions": [], "source_pool": []}

    in_news = _terms_appearing_in_articles(articles, highlighter)
    news_pool = in_news.copy()
    rng.shuffle(news_pool)

    other_pool = [t for t in glossary if t not in set(in_news)]
    rng.shuffle(other_pool)

    candidates = news_pool + other_pool
    if not candidates:
        return {"questions": [], "source_pool": []}

    questions = []
    used_terms: set[str] = set()

    for term in candidates:
        if len(questions) >= count:
            break
        if term in used_terms:
            continue

        builders = [_build_definition_question, _build_term_question]
        if term in in_news:
            builders = [_build_headline_question] + builders

        question = None
        for builder in builders:
            try:
                if builder is _build_headline_question:
                    question = builder(term, articles, glossary, rng)
                else:
                    question = builder(term, glossary, articles, rng)
                if question:
                    break
            except Exception:
                continue

        if question:
            questions.append(question)
            used_terms.add(term)

    return {
        "questions": questions,
        "source_pool": sorted(used_terms),
        "in_news_count": len([q for q in questions if q.get("article_snippet")]),
    }


if __name__ == "__main__":
    sample_articles = [
        {
            "url": "https://example.com/a",
            "title": "Senate filibuster debate",
            "source": "Test",
            "text": "The Senate's filibuster rules were at the center of debate today. "
                    "Senators discussed cloture votes and possible reconciliation paths "
                    "for the budget bill. A proposed amendment drew bipartisan support.",
        },
        {
            "url": "https://example.com/b",
            "title": "Texas redistricting map struck down",
            "source": "Test",
            "text": "A federal court ruled that the redistricting map amounts to "
                    "gerrymandering and ordered new boundaries before the next "
                    "primary election.",
        },
    ]

    print("--- Term of the day ---")
    print(pick_term_of_day(sample_articles))
    print("\n--- Quiz (3 questions) ---")
    quiz = build_quiz(sample_articles, count=3)
    for i, q in enumerate(quiz["questions"], 1):
        print(f"\nQ{i}: {q['prompt']}")
        for opt in q["options"]:
            marker = " (correct)" if opt["correct"] else ""
            print(f"  - {opt['text'][:80]}{marker}")

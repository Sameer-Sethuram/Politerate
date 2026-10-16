"""Glossary routes."""

from flask import Blueprint, jsonify, request

from backend.api import response_cache
from backend.api.validation import MAX_SEARCH_LENGTH, clean_text
from backend.db.cache import get_recent_articles

glossary_bp = Blueprint("glossary", __name__)


def recent_articles() -> list[dict]:
    """Today's articles with their text, shared by the Glossary and Learn
    pages until the next pipeline run."""
    return response_cache.cached(("recent-articles",), get_recent_articles)


def term_sources() -> dict:
    """Which of today's articles use each glossary term: a regex pass over
    every article's full text, so done once per pipeline run."""
    from backend.pipeline.highlighter import TermHighlighter
    return response_cache.cached(
        ("term-sources",), lambda: TermHighlighter().find_terms_with_sources(recent_articles()),
    )


@glossary_bp.route("/api/glossary")
def get_glossary():
    from backend.pipeline.highlighter import TermHighlighter

    search = clean_text(request.args.get("search", ""))[:MAX_SEARCH_LENGTH].lower()
    category = clean_text(request.args.get("category", ""))[:MAX_SEARCH_LENGTH].lower()

    glossary = TermHighlighter().glossary

    # Today's news only (the page says "No sources found for this term today").
    sources_by_term = term_sources()

    terms = []
    for term, info in glossary.items():
        if search and search not in term and search not in info.get("definition", ""):
            continue
        if category and info.get("category", "").lower() != category:
            continue

        term_data = {
            "term": term,
            "definition": info.get("definition", ""),
            "category": info.get("category", ""),
            "article_links": [],
        }

        if term in sources_by_term:
            for article_info in sources_by_term[term]:
                term_data["article_links"].append({
                    "source": article_info["source"],
                    "url": article_info["url"],
                    "title": article_info["title"],
                })

        terms.append(term_data)

    terms.sort(key=lambda x: x["term"])
    return jsonify({"terms": terms})


@glossary_bp.route("/api/glossary/categories")
def get_categories():
    from backend.pipeline.highlighter import TermHighlighter

    highlighter = TermHighlighter()
    categories = set()
    for info in highlighter.glossary.values():
        if info.get("category"):
            categories.add(info["category"])
    return jsonify({"categories": sorted(categories)})

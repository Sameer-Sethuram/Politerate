"""Glossary routes."""

from flask import Blueprint, jsonify, request

from backend.db.cache import get_all_articles

glossary_bp = Blueprint("glossary", __name__)


@glossary_bp.route("/api/glossary")
def get_glossary():
    from backend.pipeline.highlighter import TermHighlighter

    search = request.args.get("search", "").lower()
    category = request.args.get("category", "").lower()

    highlighter = TermHighlighter()
    glossary = highlighter.glossary

    all_articles = get_all_articles()
    term_sources = highlighter.find_terms_with_sources(all_articles)

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

        if term in term_sources:
            for article_info in term_sources[term]:
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

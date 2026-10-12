"""Archive routes — daily snapshots for the Archive page."""

from flask import Blueprint, jsonify

from backend.db.cache import (
    get_archive_day,
    get_articles_with_analysis,
    list_snapshot_dates,
    save_daily_snapshot,
)

archive_bp = Blueprint("archive", __name__)


@archive_bp.route("/api/archive")
def api_archive_list():
    return jsonify({"snapshots": list_snapshot_dates()})


@archive_bp.route("/api/archive/<date>")
def api_archive_get(date):
    """One day's topics plus that day's Daily Brief."""
    from backend.pipeline.summarizer import PoliteratePipeline

    snapshot = get_archive_day(date)
    if not snapshot:
        return jsonify({"error": "No snapshot found for that date"}), 404
    snapshot["daily_brief"] = PoliteratePipeline().build_daily_brief(snapshot["clusters"])
    return jsonify(snapshot)


@archive_bp.route("/api/archive/<date>/clusters/<cluster_id>")
def api_archive_cluster(date, cluster_id):
    """An archived topic's articles with their summaries and cached analysis.
    Fetched when the topic is expanded, since analysis payloads are large."""
    snapshot = get_archive_day(date)
    cluster = next(
        (c for c in (snapshot or {}).get("clusters", []) if str(c.get("cluster_id")) == cluster_id),
        None,
    )
    if not cluster:
        return jsonify({"error": "Topic not found for that date"}), 404

    urls = cluster.get("urls") or []
    titles = cluster.get("titles") or []
    sources = cluster.get("sources") or []
    stored = get_articles_with_analysis(urls)

    articles = []
    for i, url in enumerate(urls):
        articles.append(stored.get(url) or {
            "url": url,
            "title": titles[i] if i < len(titles) else None,
            "source": sources[i] if i < len(sources) else "Unknown",
            "summary": None,
            "credibility_score": None,
            "credibility_label": None,
            "lean": None,
            "analysis_status": "missing",
            "analysis": None,
        })

    return jsonify({"cluster_id": cluster.get("cluster_id"), "date": date, "articles": articles})


@archive_bp.route("/api/snapshot", methods=["POST"])
def api_snapshot_now():
    saved = save_daily_snapshot()
    if saved:
        return jsonify({"status": "success"})
    return jsonify({"status": "empty", "message": "No clusters to snapshot"}), 400

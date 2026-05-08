"""News / cluster JSON routes."""

import json
import logging

from flask import Blueprint, jsonify, request

from backend.db.cache import get_cached_summaries, get_cluster, is_stale
from backend.db.connection import get_connection

articles_bp = Blueprint("articles", __name__)
logger = logging.getLogger(__name__)


@articles_bp.route("/api/summaries")
def get_summaries():
    return jsonify(get_cached_summaries())


@articles_bp.route("/api/daily-summary")
def get_daily_summary():
    from backend.pipeline.summarizer import PoliteratePipeline

    cached = get_cached_summaries()
    clusters = cached.get("clusters", [])
    pipeline = PoliteratePipeline()
    daily_data = pipeline.get_daily_summary_data(clusters)
    daily_data["last_updated"] = cached.get("last_updated")
    return jsonify(daily_data)


@articles_bp.route("/api/summaries/<cluster_id>")
def get_summary(cluster_id):
    cluster = get_cluster(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
    return jsonify(cluster)


@articles_bp.route("/api/article/analysis")
def api_article_analysis():
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "url parameter required"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT url, title, source, text, credibility_score, credibility_label,
               analysis_json, article_json, bias_label, dominant_emotion,
               subjectivity_ratio, analysis_status, analyzed_at
        FROM articles WHERE url = ?
    """, (url,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Article not found"}), 404

    def _parse(val):
        if not val:
            return None
        try:
            return json.loads(val)
        except (ValueError, TypeError):
            return None

    return jsonify({
        "url": row["url"],
        "title": row["title"],
        "source": row["source"],
        "credibility_score": row["credibility_score"],
        "credibility_label": row["credibility_label"],
        "bias_label": row["bias_label"],
        "dominant_emotion": row["dominant_emotion"],
        "subjectivity_ratio": row["subjectivity_ratio"],
        "analysis_status": row["analysis_status"],
        "analyzed_at": row["analyzed_at"],
        "chunks": _parse(row["analysis_json"]),
        "article_summary": _parse(row["article_json"]),
        "text": row["text"],
    })


@articles_bp.route("/api/all-articles")
def get_all_articles():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT url, title, source, credibility_score, credibility_label,
               bias_label, analysis_status, cluster_id, scraped_at
        FROM articles
        WHERE url IS NOT NULL AND url != ''
        ORDER BY scraped_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    articles = []
    for row in rows:
        cid = row["cluster_id"] or ""
        in_summary = bool(cid) and not cid.startswith("singleton_")
        lean = next(
            (v for v in (row["credibility_label"], row["bias_label"])
             if v and v != "unknown"),
            None
        )
        articles.append({
            "url": row["url"],
            "title": row["title"],
            "source": row["source"],
            "credibility_score": row["credibility_score"],
            "lean": lean,
            "analysis_status": row["analysis_status"],
            "in_summary": in_summary,
            "scraped_at": row["scraped_at"],
        })

    return jsonify({"articles": articles, "total": len(articles)})


@articles_bp.route("/api/cluster/<cluster_id>/analysis")
def api_cluster_analysis(cluster_id):
    """Return per-article DeBERTa analysis for a cluster.

    Reads `articles.analysis_json` / `articles.article_json` populated by
    the pipeline's credibility filter. Never runs live inference — running
    DeBERTa synchronously per article on CPU would block the request for
    minutes. If a particular article doesn't have cached analysis yet
    (analysis_status=pending), we surface that to the UI so it shows
    'Analysis pending' instead of a forever-spinning placeholder.
    """
    cluster = get_cluster(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    articles_out = []
    cached_count = 0
    pending_count = 0
    for article in cluster.get("articles", []):
        entry = {
            "url": article.get("url"),
            "title": article.get("title"),
            "source": article.get("source"),
            "credibility_score": article.get("credibility_score"),
            "credibility_label": article.get("credibility_label"),
            "analysis": None,
            "analysis_status": article.get("analysis_status") or "pending",
        }

        chunks_raw = article.get("analysis_json")
        article_agg_raw = article.get("article_json")
        if chunks_raw or article_agg_raw:
            try:
                chunks = json.loads(chunks_raw) if chunks_raw else []
                article_agg = json.loads(article_agg_raw) if article_agg_raw else {}
                entry["analysis"] = {"chunks": chunks, "article": article_agg}
                entry["analysis_status"] = "done"
                cached_count += 1
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse cached analysis for {article.get('url')}: {e}")
                entry["analysis_error"] = "cached analysis is malformed"
                pending_count += 1
        else:
            pending_count += 1

        articles_out.append(entry)

    logger.info(
        f"Cluster {cluster_id} analysis: {cached_count} cached, "
        f"{pending_count} pending (no live inference)"
    )

    return jsonify({
        "cluster_id": cluster.get("cluster_id"),
        "model_version": "cached",
        "cached_count": cached_count,
        "pending_count": pending_count,
        "articles": articles_out,
    })

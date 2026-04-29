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
    from backend.api.main import run_pipeline_update
    if is_stale():
        run_pipeline_update()
    return jsonify(get_cached_summaries())


@articles_bp.route("/api/daily-summary")
def get_daily_summary():
    from backend.api.main import run_pipeline_update
    from backend.pipeline.summarizer import PoliteratePipeline

    if is_stale():
        run_pipeline_update()

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
    from backend.inference import get_analyzer

    cluster = get_cluster(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    analyzer = get_analyzer()
    articles_out = []
    for article in cluster.get("articles", []):
        text = (article.get("text") or "").strip()
        entry = {
            "url": article.get("url"),
            "title": article.get("title"),
            "source": article.get("source"),
            "credibility_score": article.get("credibility_score"),
            "credibility_label": article.get("credibility_label"),
            "analysis": None,
        }
        if len(text) >= 50:
            try:
                entry["analysis"] = analyzer.predict_article(text)
            except Exception as e:
                logger.warning(f"Analyzer failed for {article.get('url')}: {e}")
                entry["analysis_error"] = str(e)[:120]
        articles_out.append(entry)

    return jsonify({
        "cluster_id": cluster.get("cluster_id"),
        "model_version": getattr(analyzer, "model_version", "unknown"),
        "articles": articles_out,
    })

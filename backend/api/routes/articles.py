"""News / cluster JSON routes."""

import logging

from flask import Blueprint, jsonify

from backend.db.cache import get_cached_summaries, get_cluster, is_stale

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

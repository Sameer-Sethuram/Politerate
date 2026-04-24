"""System routes: refresh + status."""

from flask import Blueprint, jsonify

from backend.db.cache import (
    clear_cache,
    get_article_count,
    get_last_refresh,
    is_stale,
)

system_bp = Blueprint("system", __name__)


@system_bp.route("/api/refresh", methods=["POST"])
def refresh():
    from backend.api.main import run_pipeline_update

    clear_cache()
    success = run_pipeline_update()
    if success:
        return jsonify({"status": "success", "message": "Summaries refreshed"})
    return jsonify({"status": "error", "message": "Refresh failed"}), 500


@system_bp.route("/api/status")
def status():
    return jsonify({
        "last_updated": get_last_refresh(),
        "article_count": get_article_count(),
        "is_stale": is_stale(),
    })

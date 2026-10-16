"""System routes: refresh, status, health check and browser error reports."""

import logging

from flask import Blueprint, jsonify, request

from backend.api import response_cache
from backend.api.limits import MINUTE, rate_limit, require_admin
from backend.config import HEALTH_MAX_REFRESH_HOURS
from backend.db.cache import (
    clear_cache,
    get_article_count,
    get_last_refresh,
    is_stale,
    refresh_age_hours,
)

system_bp = Blueprint("system", __name__)
logger = logging.getLogger(__name__)


@system_bp.route("/api/refresh", methods=["POST"])
@require_admin
def refresh():
    """Delete every stored article and topic, then rebuild them with a full
    pipeline run (many minutes). Admin only: it wipes the cached summaries
    and analyses, which take hours of CPU to regenerate."""
    from backend.api.main import pipeline_running, run_pipeline_update

    if pipeline_running():
        return jsonify({"status": "busy", "message": "A pipeline run is already in progress"}), 409
    clear_cache()
    response_cache.clear()
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


@system_bp.route("/api/health")
def health():
    """For uptime monitoring: 200 while the site is serving fresh news, 503
    when the database can't be read or the hourly pipeline has stopped
    finishing runs (the site would keep showing old news)."""
    from backend.api.main import pipeline_running

    try:
        age = refresh_age_hours()
    except Exception:
        logger.exception("Health check could not read the database")
        response = jsonify({"status": "down", "problems": ["database unreadable"]})
        response.status_code = 503
        response.headers["Cache-Control"] = "no-store"
        return response

    problems = []
    if age is None:
        problems.append("the pipeline has never finished a run")
    elif age > HEALTH_MAX_REFRESH_HOURS:
        problems.append(f"no pipeline run has finished in {age:.1f} hours")

    response = jsonify({
        "status": "degraded" if problems else "ok",
        "problems": problems,
        "hours_since_refresh": round(age, 2) if age is not None else None,
        "pipeline_running": pipeline_running(),
    })
    response.status_code = 503 if problems else 200
    response.headers["Cache-Control"] = "no-store"
    return response


def _one_line(value, limit: int) -> str:
    # Collapses newlines so a report can't forge extra log lines.
    return " ".join(str(value or "").split())[:limit]


@system_bp.route("/api/client-errors", methods=["POST"])
@rate_limit("client-errors", (10, MINUTE))
def client_error():
    """Errors from visitors' browsers (the frontend's error page and
    uncaught-error listeners post here), which otherwise never reach the
    server's logs."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Send the error as JSON"}), 400
    stack = "\n".join("    " + _one_line(line, 300) for line in str(data.get("stack") or "").splitlines()[:30])
    logger.warning(
        f"Browser error on {_one_line(data.get('page'), 300)}: {_one_line(data.get('message'), 500)}"
        f" [{_one_line(request.headers.get('User-Agent'), 200)}]" + (f"\n{stack}" if stack else "")
    )
    return "", 204

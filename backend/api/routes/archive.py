"""Archive routes — daily snapshots for the Archive page."""

from flask import Blueprint, jsonify

from backend.db.cache import (
    get_snapshot,
    list_snapshot_dates,
    save_daily_snapshot,
)

archive_bp = Blueprint("archive", __name__)


@archive_bp.route("/api/archive")
def api_archive_list():
    return jsonify({"snapshots": list_snapshot_dates()})


@archive_bp.route("/api/archive/<date>")
def api_archive_get(date):
    snapshot = get_snapshot(date)
    if not snapshot:
        return jsonify({"error": "No snapshot found for that date"}), 404
    return jsonify(snapshot)


@archive_bp.route("/api/snapshot", methods=["POST"])
def api_snapshot_now():
    saved = save_daily_snapshot()
    if saved:
        return jsonify({"status": "success"})
    return jsonify({"status": "empty", "message": "No clusters to snapshot"}), 400

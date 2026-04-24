"""Text analyzer + summarize routes."""

import logging

from flask import Blueprint, jsonify, request

analyze_bp = Blueprint("analyze", __name__)
logger = logging.getLogger(__name__)


@analyze_bp.route("/api/analyze", methods=["POST"])
def api_analyze():
    from backend.inference import get_analyzer

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if len(text) < 50:
        return jsonify({"error": "Text must be at least 50 characters"}), 400
    if len(text) > 50_000:
        return jsonify({"error": "Text exceeds 50,000 characters"}), 400

    try:
        analyzer = get_analyzer()
        result = analyzer.predict_article(text)
        result["cached"] = False
        result["model_version"] = getattr(analyzer, "model_version", "unknown")
        return jsonify(result)
    except Exception as e:
        logger.exception("Analyzer failed")
        return jsonify({"error": f"Analysis failed: {e}"}), 500


@analyze_bp.route("/api/summarize", methods=["POST"])
def summarize():
    from backend.api.main import generate_summary

    data = request.json or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400
    return jsonify({"summary": generate_summary(text)})

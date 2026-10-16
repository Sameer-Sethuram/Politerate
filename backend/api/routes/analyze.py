"""Text analyzer + summarize routes."""

import logging

from flask import Blueprint, jsonify, request

from backend.api.limits import HOUR, MINUTE, inference_slot, rate_limit
from backend.api.validation import clean_text

analyze_bp = Blueprint("analyze", __name__)
logger = logging.getLogger(__name__)

MIN_ANALYZE_CHARS = 50
MAX_ANALYZE_CHARS = 50_000
# BART reads only its first 1,024 tokens (~5,000 characters) anyway.
MAX_SUMMARIZE_CHARS = 20_000


@analyze_bp.route("/api/analyze", methods=["POST"])
@rate_limit("analyze", (10, MINUTE), (100, HOUR))
@inference_slot
def api_analyze():
    from backend.inference import get_analyzer

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        return jsonify({"error": 'Send JSON with the text to analyze as "text".'}), 400
    text = clean_text(data["text"])
    if len(text) < MIN_ANALYZE_CHARS:
        return jsonify({"error": f"Text must be at least {MIN_ANALYZE_CHARS} characters"}), 400
    if len(text) > MAX_ANALYZE_CHARS:
        return jsonify({"error": f"Text exceeds {MAX_ANALYZE_CHARS:,} characters"}), 400

    try:
        analyzer = get_analyzer()
        result = analyzer.predict_article(text)
        result["cached"] = False
        result["model_version"] = getattr(analyzer, "model_version", "unknown")
        return jsonify(result)
    except Exception:
        logger.exception("Analyzer failed")
        return jsonify({"error": "Analysis failed on our side. Please try again in a moment."}), 500


@analyze_bp.route("/api/summarize", methods=["POST"])
@rate_limit("summarize", (10, MINUTE), (100, HOUR))
@inference_slot
def summarize():
    from backend.api.main import generate_summary

    data = request.get_json(silent=True)
    text = clean_text(data.get("text")) if isinstance(data, dict) else ""
    if not text:
        return jsonify({"error": "No text provided"}), 400
    if len(text) > MAX_SUMMARIZE_CHARS:
        return jsonify({"error": f"Text exceeds {MAX_SUMMARIZE_CHARS:,} characters"}), 400
    return jsonify({"summary": generate_summary(text)})

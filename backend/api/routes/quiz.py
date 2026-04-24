"""Learn-page routes: quiz generator and term-of-day."""

from flask import Blueprint, jsonify, request

from backend.db.cache import get_all_articles

quiz_bp = Blueprint("quiz", __name__)


@quiz_bp.route("/api/quiz")
def api_quiz():
    from backend.quiz.generator import build_quiz
    count = int(request.args.get("count", 5))
    return jsonify(build_quiz(get_all_articles(), count=count))


@quiz_bp.route("/api/term-of-day")
def api_term_of_day():
    from backend.quiz.generator import pick_term_of_day
    return jsonify(pick_term_of_day(get_all_articles()))

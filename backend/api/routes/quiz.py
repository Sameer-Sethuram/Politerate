"""Learn-page routes: quiz generator and term-of-day."""

from flask import Blueprint, jsonify, request

from backend.api.routes.glossary import recent_articles, term_sources
from backend.api.validation import bounded_int

quiz_bp = Blueprint("quiz", __name__)

MAX_QUIZ_QUESTIONS = 20


@quiz_bp.route("/api/quiz")
def api_quiz():
    from backend.quiz.generator import build_quiz
    count = bounded_int(request.args.get("count"), default=5, low=1, high=MAX_QUIZ_QUESTIONS)
    return jsonify(build_quiz(recent_articles(), count=count, term_sources=term_sources()))


@quiz_bp.route("/api/term-of-day")
def api_term_of_day():
    from backend.quiz.generator import pick_term_of_day
    return jsonify(pick_term_of_day(recent_articles(), term_sources=term_sources()))

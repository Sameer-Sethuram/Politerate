"""
webapp.py

Flask web application for Politerate.
Serves auto-generated news summaries with topic clustering and political term highlighting.
"""

import logging
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler

from cache import (
    init_db,
    get_cached_summaries,
    get_cluster,
    get_all_articles,
    is_stale,
    get_last_refresh,
    get_article_count,
    update_last_refresh,
    clear_cache,
    save_daily_snapshot,
    get_snapshot,
    list_snapshot_dates,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

scheduler = BackgroundScheduler()

# Resolve BART summarization model. Priority:
#   1. POLITERATE_MODEL env var (explicit override)
#   2. Local fine_tuned_bart_news/ if present (dev machines where you trained it)
#   3. Hugging Face Hub repo (fresh clones auto-download)
HF_MODEL_ID = "sameersethuram/politerate-bart-news"
_LOCAL_MODEL_DIR = Path(__file__).resolve().parent / "fine_tuned_bart_news"
MODEL_PATH = (
    os.environ.get("POLITERATE_MODEL")
    or (str(_LOCAL_MODEL_DIR) if _LOCAL_MODEL_DIR.exists() else HF_MODEL_ID)
)

_model = None
_tokenizer = None


def load_model():
    global _model, _tokenizer
    try:
        from transformers import BartForConditionalGeneration, BartTokenizer
        import torch

        logger.info("Loading summarization model...")
        _tokenizer = BartTokenizer.from_pretrained(MODEL_PATH)
        _model = BartForConditionalGeneration.from_pretrained(MODEL_PATH)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = _model.to(device)
        _model.eval()
        logger.info(f"Model loaded on {device}")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")


def run_pipeline_update():
    from pipeline import PoliteratePipeline

    logger.info("Starting scheduled pipeline update...")
    try:
        pipeline = PoliteratePipeline(model_path=MODEL_PATH)
        pipeline.load_model()
        results = pipeline.run()

        from cache import save_clusters
        save_clusters(results.get("clusters", []))

        update_last_refresh()
        logger.info(f"Pipeline update complete. Stats: {results.get('stats', {})}")
        return True
    except Exception as e:
        logger.error(f"Pipeline update failed: {e}")
        return False


def generate_summary(text, max_length=150, min_length=50):
    if not _model:
        return "[Summary unavailable - model not loaded]"

    from transformers import BartTokenizer
    import torch

    inputs = _tokenizer(
        text,
        max_length=1024,
        truncation=True,
        return_tensors="pt"
    ).to(_model.device)

    summary_ids = _model.generate(
        inputs["input_ids"],
        num_beams=4,
        max_length=max_length,
        min_length=min_length,
        early_stopping=True
    )

    return _tokenizer.decode(summary_ids[0], skip_special_tokens=True)


def scheduled_job():
    if is_stale():
        logger.info("Cache is stale, running pipeline update...")
        run_pipeline_update()
    else:
        logger.info("Cache is fresh, skipping update")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/glossary")
def glossary():
    return render_template("glossary.html")


@app.route("/archive")
def archive():
    return render_template("archive.html")


@app.route("/learn")
def learn():
    return render_template("learn.html")


@app.route("/analyzer")
def analyzer():
    return render_template("analyzer.html")


@app.route("/cluster/<cluster_id>")
def cluster_detail(cluster_id):
    cluster = get_cluster(cluster_id)
    if not cluster:
        return render_template("cluster.html", cluster=None, cluster_id=cluster_id), 404
    return render_template("cluster.html", cluster=cluster, cluster_id=cluster_id)


@app.route("/api/summaries")
def get_summaries():
    if is_stale():
        run_pipeline_update()

    data = get_cached_summaries()
    return jsonify(data)


@app.route("/api/daily-summary")
def get_daily_summary():
    if is_stale():
        run_pipeline_update()

    from pipeline import PoliteratePipeline
    cached = get_cached_summaries()
    clusters = cached.get("clusters", [])

    pipeline = PoliteratePipeline()
    daily_data = pipeline.get_daily_summary_data(clusters)

    daily_data["last_updated"] = cached.get("last_updated")

    return jsonify(daily_data)


@app.route("/api/summaries/<cluster_id>")
def get_summary(cluster_id):
    cluster = get_cluster(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
    return jsonify(cluster)


@app.route("/api/cluster/<cluster_id>/analysis")
def api_cluster_analysis(cluster_id):
    from credibility import get_analyzer
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


@app.route("/api/refresh", methods=["POST"])
def refresh():
    clear_cache()
    success = run_pipeline_update()
    if success:
        return jsonify({"status": "success", "message": "Summaries refreshed"})
    else:
        return jsonify({"status": "error", "message": "Refresh failed"}), 500


@app.route("/api/status")
def status():
    return jsonify({
        "last_updated": get_last_refresh(),
        "article_count": get_article_count(),
        "is_stale": is_stale()
    })


@app.route("/api/glossary")
def get_glossary():
    from politerate import TermHighlighter, DEFAULT_GLOSSARY

    search = request.args.get("search", "").lower()
    category = request.args.get("category", "").lower()

    highlighter = TermHighlighter()
    glossary = highlighter.glossary

    all_articles = get_all_articles()
    term_sources = highlighter.find_terms_with_sources(all_articles)

    terms = []
    for term, info in glossary.items():
        if search and search not in term and search not in info.get("definition", ""):
            continue
        if category and info.get("category", "").lower() != category:
            continue

        term_data = {
            "term": term,
            "definition": info.get("definition", ""),
            "category": info.get("category", ""),
            "article_links": []
        }

        if term in term_sources:
            for article_info in term_sources[term]:
                term_data["article_links"].append({
                    "source": article_info["source"],
                    "url": article_info["url"],
                    "title": article_info["title"]
                })

        terms.append(term_data)

    terms.sort(key=lambda x: x["term"])

    return jsonify({"terms": terms})


@app.route("/api/glossary/categories")
def get_categories():
    from politerate import TermHighlighter

    highlighter = TermHighlighter()
    categories = set()
    for info in highlighter.glossary.values():
        if info.get("category"):
            categories.add(info["category"])

    return jsonify({"categories": sorted(categories)})


@app.route("/api/archive")
def api_archive_list():
    return jsonify({"snapshots": list_snapshot_dates()})


@app.route("/api/archive/<date>")
def api_archive_get(date):
    snapshot = get_snapshot(date)
    if not snapshot:
        return jsonify({"error": "No snapshot found for that date"}), 404
    return jsonify(snapshot)


@app.route("/api/snapshot", methods=["POST"])
def api_snapshot_now():
    saved = save_daily_snapshot()
    if saved:
        return jsonify({"status": "success"})
    return jsonify({"status": "empty", "message": "No clusters to snapshot"}), 400


@app.route("/api/quiz")
def api_quiz():
    from politerate_quiz import build_quiz
    count = int(request.args.get("count", 5))
    quiz = build_quiz(get_all_articles(), count=count)
    return jsonify(quiz)


@app.route("/api/term-of-day")
def api_term_of_day():
    from politerate_quiz import pick_term_of_day
    return jsonify(pick_term_of_day(get_all_articles()))


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    from credibility import get_analyzer
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


@app.route("/api/summarize", methods=["POST"])
def summarize():
    data = request.json
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    summary = generate_summary(text)
    return jsonify({"summary": summary})


def daily_snapshot_job():
    logger.info("Running end-of-day snapshot job...")
    try:
        save_daily_snapshot()
    except Exception as e:
        logger.error(f"Snapshot job failed: {e}")


def start_scheduler():
    scheduler.add_job(
        func=scheduled_job,
        trigger="interval",
        hours=1,
        id="pipeline_refresh",
        name="Refresh summaries hourly",
        replace_existing=True
    )
    scheduler.add_job(
        func=daily_snapshot_job,
        trigger="cron",
        hour=23,
        minute=55,
        id="daily_snapshot",
        name="End-of-day snapshot",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started - hourly refresh + 23:55 snapshot")


def initialize():
    init_db()
    load_model()

    if is_stale():
        logger.info("Cache is stale on startup - running initial pipeline...")
        run_pipeline_update()

    start_scheduler()


if __name__ == "__main__":
    initialize()
    app.run(debug=True, port=5000)

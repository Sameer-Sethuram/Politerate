"""
webapp.py

Flask web application for Politerate.
Serves auto-generated news summaries with topic clustering and political term highlighting.
"""

import logging
from flask import Flask, jsonify, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler

from cache import (
    init_db,
    get_cached_summaries,
    get_cluster,
    is_stale,
    get_last_refresh,
    get_article_count,
    update_last_refresh,
    clear_cache
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

scheduler = BackgroundScheduler()
MODEL_PATH = "./fine_tuned_bart_news"

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


@app.route("/api/refresh", methods=["POST"])
def refresh():
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

    cached = get_cached_summaries()
    all_articles = []
    for cluster in cached.get("clusters", []):
        for article in cluster.get("articles", []):
            all_articles.append(article)

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


@app.route("/api/summarize", methods=["POST"])
def summarize():
    data = request.json
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    summary = generate_summary(text)
    return jsonify({"summary": summary})


def start_scheduler():
    scheduler.add_job(
        func=scheduled_job,
        trigger="interval",
        hours=1,
        id="pipeline_refresh",
        name="Refresh summaries hourly",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started - pipeline will refresh hourly")


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

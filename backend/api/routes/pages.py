"""HTML page routes (Jinja templates)."""

from flask import Blueprint, render_template

from backend.db.cache import get_cluster

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    return render_template("index.html")


@pages_bp.route("/glossary")
def glossary():
    return render_template("glossary.html")


@pages_bp.route("/archive")
def archive():
    return render_template("archive.html")


@pages_bp.route("/learn")
def learn():
    return render_template("learn.html")


@pages_bp.route("/analyzer")
def analyzer():
    return render_template("analyzer.html")


@pages_bp.route("/cluster/<cluster_id>")
def cluster_detail(cluster_id):
    cluster = get_cluster(cluster_id)
    if not cluster:
        return render_template("cluster.html", cluster=None, cluster_id=cluster_id), 404
    return render_template("cluster.html", cluster=cluster, cluster_id=cluster_id)

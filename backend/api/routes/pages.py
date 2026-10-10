"""Serves the React frontend build (frontend/dist).

Every non-API path returns index.html so React Router can handle client-side
routes (/glossary, /cluster/<id>, ...). Built assets under dist/ are served
directly. /api/* routes are registered on their own blueprints and take
precedence over the catch-all.
"""

import os

from flask import Blueprint, abort, send_from_directory
from werkzeug.security import safe_join

from backend.config import FRONTEND_DIST_DIR

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", defaults={"path": ""})
@pages_bp.route("/<path:path>")
def spa(path):
    # Unknown API paths should 404, not fall through to the SPA shell.
    if path.startswith("api/"):
        abort(404)

    if path:
        asset = safe_join(str(FRONTEND_DIST_DIR), path)
        if asset and os.path.isfile(asset):
            return send_from_directory(FRONTEND_DIST_DIR, path)

    if not (FRONTEND_DIST_DIR / "index.html").is_file():
        return (
            "Frontend not built. Run `npm install && npm run build` in frontend/.",
            503,
            {"Content-Type": "text/plain; charset=utf-8"},
        )
    return send_from_directory(FRONTEND_DIST_DIR, "index.html", max_age=0)

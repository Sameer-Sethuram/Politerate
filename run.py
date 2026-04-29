"""
run.py

Entrypoint for the Politerate Flask app. Kept thin so the application
factory lives in `backend/api/main.py` (mirroring Sarah's layout).

    python run.py            # development
    gunicorn run:app         # production
"""

import os

from backend.api.main import create_app, initialize

DEBUG = os.environ.get("POLITERATE_DEBUG", "1") != "0"
PORT = int(os.environ.get("POLITERATE_PORT", "5000"))

app = create_app()

# Initialize on import unless we're in the dev parent reloader process.
# The Werkzeug reloader spawns a child where WERKZEUG_RUN_MAIN=true; we
# only want to load the heavy bits in the child to avoid double-loading.
# When run under gunicorn, there is no reloader, so initialize runs at import.
_is_dev_parent = DEBUG and os.environ.get("WERKZEUG_RUN_MAIN") != "true"

if not _is_dev_parent:
    initialize()


if __name__ == "__main__":
    app.run(debug=DEBUG, port=PORT)


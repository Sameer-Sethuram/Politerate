"""
run.py

Entrypoint for the Politerate Flask app. Kept thin so the application
factory lives in `backend/api/main.py` (mirroring Sarah's layout).

    python run.py
"""

import os

from backend.api.main import create_app, initialize

DEBUG = os.environ.get("POLITERATE_DEBUG", "1") != "0"
PORT = int(os.environ.get("POLITERATE_PORT", "5000"))

app = create_app()

if __name__ == "__main__":
    # Flask's debug reloader spawns a parent + child process. Only run the
    # heavy initialize() (DB init, BART load, pipeline pre-warm, scheduler)
    # in the child (WERKZEUG_RUN_MAIN=true). When DEBUG is off there's no
    # reloader, so initialize once in the main process.
    if not DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        initialize()
    app.run(debug=DEBUG, port=PORT)

"""
api/index.py — Vercel Serverless Entry Point for UniSync

Vercel looks for the `app` object in this file.
All paths are resolved using absolute references so Flask
can locate templates/ and static/ correctly from any working directory.
"""

import sys
import os

# ── Path bootstrap ────────────────────────────────────────────────────────────
# __file__ is  /var/task/api/index.py  inside the Vercel Lambda.
# The project root (where app/, core/, templates/, static/ live) is one level up.

_HERE        = os.path.dirname(os.path.abspath(__file__))   # …/api
_PROJECT_ROOT = os.path.dirname(_HERE)                       # …/ (repo root)

# Make sure the repo root is on sys.path so `from app import …` works.
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ── Create the Flask app ──────────────────────────────────────────────────────
from app import create_app   # noqa: E402  (import after path fix)

app = create_app(os.environ.get("FLASK_ENV", "production"))

# Vercel calls the WSGI `app` object directly; the block below is
# only for local testing (`python api/index.py`).
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )
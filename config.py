"""
config.py
═════════
Flask configuration.

All sensitive values come from environment variables.
On Vercel: set these in Project Settings → Environment Variables.
Locally:   create a .env file (see .env.example).

NO .env file is committed to git — that is correct and intentional.
"""

import os

# Load .env only when running locally (python-dotenv ignores missing file)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    # ── Core ──────────────────────────────────────────────────
    SECRET_KEY       = os.environ.get("FLASK_SECRET_KEY", "change-me-in-vercel-env")
    APP_NAME         = os.environ.get("APP_NAME",         "UniSync")
    UNIVERSITY_NAME  = os.environ.get("UNIVERSITY_NAME",  "Rabindra University, Bangladesh")
    DEPARTMENT_NAME  = os.environ.get("DEPARTMENT_NAME",  "Department of Management")

    # ── Supabase ──────────────────────────────────────────────
    SUPABASE_URL         = os.environ.get("SUPABASE_URL",          "")
    SUPABASE_ANON_KEY    = os.environ.get("SUPABASE_ANON_KEY",     "")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY",  "")

    # ── Flask-Mail (SMTP) ─────────────────────────────────────
    # Gmail: use an App Password (NOT your normal Gmail password).
    # Set these in Vercel Dashboard → Project → Settings → Environment Variables
    MAIL_SERVER         = os.environ.get("MAIL_SERVER",         "smtp.gmail.com")
    MAIL_PORT           = int(os.environ.get("MAIL_PORT",       "587"))
    MAIL_USE_TLS        = os.environ.get("MAIL_USE_TLS",        "True") == "True"
    MAIL_USERNAME       = os.environ.get("MAIL_USERNAME",       "")
    MAIL_PASSWORD       = os.environ.get("MAIL_PASSWORD",       "")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER",
        os.environ.get("MAIL_USERNAME", "")
    )

    # ── Web Push (VAPID) ──────────────────────────────────────
    # Generate once with: python3 -c "from pywebpush import Vapid; v=Vapid(); v.generate_keys(); print('Private:',v.private_key); print('Public:',v.public_key)"
    # Or use: https://web-push-codelab.glitch.me
    VAPID_PUBLIC_KEY  = os.environ.get("VAPID_PUBLIC_KEY",  "")
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")

    # ── APScheduler ───────────────────────────────────────────
    # NOT used — email scheduling is done via Vercel Cron Jobs.
    # Kept here only so Flask-APScheduler import does not crash.
    SCHEDULER_API_ENABLED = False
    SCHEDULER_ENABLED     = False   # always False — Vercel Cron handles this

    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "default":     DevelopmentConfig,
}
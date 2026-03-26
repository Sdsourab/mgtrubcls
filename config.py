"""
config.py — UniSync Configuration

All secrets are read from environment variables so that:
  • Local dev  → values in a .env file (loaded by python-dotenv / shell)
  • Vercel prod → values set in the Vercel Dashboard → Settings → Environment Variables

NEVER hard-code real keys here.  The defaults below are empty strings;
the app will raise a clear error at startup if required vars are missing.
"""

import os


class Config:
    # ── Flask core ────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

    # ── Supabase ──────────────────────────────────────────────────────────────
    SUPABASE_URL         = os.environ.get("SUPABASE_URL", "")
    SUPABASE_ANON_KEY    = os.environ.get("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

    # ── App metadata ──────────────────────────────────────────────────────────
    APP_NAME        = "UniSync"
    UNIVERSITY_NAME = "Rabindra University, Bangladesh"
    DEPARTMENT_NAME = "Department of Management"

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
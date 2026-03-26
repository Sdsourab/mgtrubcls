"""
config.py — UniSync Configuration

Secrets are read from environment variables (Vercel Dashboard → Settings → Environment Variables).
Falls back to hardcoded values so the app works even if env vars are not yet configured.
"""

import os

# ── Fallback keys (used if env vars not set) ──────────────────────────────────
_URL  = "https://akitkwaeotifdujkoykd.supabase.co"
_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFraXRrd2Flb3RpZmR1amtveWtkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ0NDI1NjMsImV4cCI6MjA5MDAxODU2M30.TcIXK8pt01shOniRaAHKK8It1RJ3NyXSqB9RAEgBvC0"
_SVC  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFraXRrd2Flb3RpZmR1amtveWtkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDQ0MjU2MywiZXhwIjoyMDkwMDE4NTYzfQ.7nrr4aDxKFR3CNwhOPEbeUY5XcEpeNguOU05Fk4-9w4"


class Config:
    # ── Flask core ────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "unisync-secret-2026")

    # ── Supabase ──────────────────────────────────────────────────────────────
    SUPABASE_URL         = os.environ.get("SUPABASE_URL", _URL)
    SUPABASE_ANON_KEY    = os.environ.get("SUPABASE_ANON_KEY", _ANON)
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", _SVC)

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
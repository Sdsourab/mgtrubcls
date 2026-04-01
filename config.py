"""
config.py — UniSync Flask Configuration
Email: Resend API (resend.com)
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    # ── Flask ────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-in-prod')

    # ── Supabase ─────────────────────────────────────────────
    SUPABASE_URL         = os.environ.get('SUPABASE_URL',         '')
    SUPABASE_ANON_KEY    = os.environ.get('SUPABASE_ANON_KEY',    '')
    SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')

    # ── Resend Email ─────────────────────────────────────────
    # resend.com → API Keys → Create API Key → copy it
    RESEND_API_KEY   = os.environ.get('RESEND_API_KEY', '')

    # Sender: "UniSync <onboarding@resend.dev>"
    # onboarding@resend.dev is Resend's built-in test sender — works immediately.
    # After domain verification, change to your own domain.
    MAIL_FROM = os.environ.get(
        'MAIL_FROM',
        'UniSync <onboarding@resend.dev>'
    )

    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
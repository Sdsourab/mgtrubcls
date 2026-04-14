"""
config.py — UniSync Flask Configuration
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    # ── Flask ─────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-in-prod')

    # ── Supabase ──────────────────────────────────────────────
    SUPABASE_URL         = os.environ.get('SUPABASE_URL',         '')
    SUPABASE_ANON_KEY    = os.environ.get('SUPABASE_ANON_KEY',    '')
    SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')

    # ── Resend Email ──────────────────────────────────────────
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
    MAIL_FROM      = os.environ.get('MAIL_FROM', 'UniSync <onboarding@resend.dev>')

    # ── Web Push (VAPID) ──────────────────────────────────────
    # Generate once with: python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); print(v.private_pem().decode()); print(v.public_key.public_bytes_raw().hex())"
    # Or use web-push-codelab.glitch.me/vapid-keygen
    VAPID_PRIVATE_KEY   = os.environ.get('VAPID_PRIVATE_KEY',   '')   # base64url PEM
    VAPID_PUBLIC_KEY    = os.environ.get('VAPID_PUBLIC_KEY',    '')   # base64url
    VAPID_CLAIMS_EMAIL  = os.environ.get('VAPID_CLAIMS_EMAIL',  'admin@unisync.edu.bd')

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
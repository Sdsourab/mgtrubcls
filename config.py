"""
config.py
══════════
Flask configuration for UniSync.

Email এর জন্য Brevo (smtp-relay.brevo.com) ব্যবহার করা হচ্ছে।
Flask-Mail নেই — Python built-in smtplib দিয়ে সরাসরি send করা হয়।

Vercel এ Environment Variables:
  BREVO_SMTP_LOGIN   → Brevo account email
  BREVO_SMTP_KEY     → Brevo → SMTP & API → SMTP → Password (key)
  MAIL_FROM_NAME     → "UniSync" (optional, default: UniSync)
  MAIL_FROM_EMAIL    → sender email (Brevo verified email)
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    # ── Core ──────────────────────────────────────────────────
    SECRET_KEY           = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-in-prod')
    APP_NAME             = 'UniSync'

    # ── Supabase ──────────────────────────────────────────────
    SUPABASE_URL         = os.environ.get('SUPABASE_URL',         '')
    SUPABASE_ANON_KEY    = os.environ.get('SUPABASE_ANON_KEY',    '')
    SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')

    # ── Brevo SMTP ────────────────────────────────────────────
    # Brevo Dashboard → SMTP & API → SMTP tab
    BREVO_SMTP_HOST  = 'smtp-relay.brevo.com'
    BREVO_SMTP_PORT  = 587
    BREVO_SMTP_LOGIN = os.environ.get('BREVO_SMTP_LOGIN', '')   # Brevo account email
    BREVO_SMTP_KEY   = os.environ.get('BREVO_SMTP_KEY',   '')   # Brevo SMTP password/key
    MAIL_FROM_NAME   = os.environ.get('MAIL_FROM_NAME',   'UniSync')
    MAIL_FROM_EMAIL  = os.environ.get('MAIL_FROM_EMAIL',  os.environ.get('BREVO_SMTP_LOGIN', ''))

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
"""
config.py — Flask Configuration
সব values Vercel Environment Variables থেকে আসে।
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    SECRET_KEY           = os.environ.get("FLASK_SECRET_KEY", "change-me")
    SUPABASE_URL         = os.environ.get("SUPABASE_URL",         "")
    SUPABASE_ANON_KEY    = os.environ.get("SUPABASE_ANON_KEY",    "")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

    # Email (Gmail App Password অথবা Brevo SMTP)
    MAIL_SERVER         = os.environ.get("MAIL_SERVER",         "smtp.gmail.com")
    MAIL_PORT           = int(os.environ.get("MAIL_PORT",       "587"))
    MAIL_USE_TLS        = os.environ.get("MAIL_USE_TLS",        "True") == "True"
    MAIL_USERNAME       = os.environ.get("MAIL_USERNAME",       "")
    MAIL_PASSWORD       = os.environ.get("MAIL_PASSWORD",       "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "")

    SCHEDULER_API_ENABLED = False
    SCHEDULER_ENABLED     = False
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
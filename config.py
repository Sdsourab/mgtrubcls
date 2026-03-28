import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Core
    SECRET_KEY          = os.environ.get('FLASK_SECRET_KEY', 'dev-fallback-key')
    APP_NAME            = os.environ.get('APP_NAME', 'UniSync')
    UNIVERSITY_NAME     = os.environ.get('UNIVERSITY_NAME', 'Rabindra University, Bangladesh')
    DEPARTMENT_NAME     = os.environ.get('DEPARTMENT_NAME', 'Department of Management')

    # Supabase
    SUPABASE_URL        = os.environ.get('SUPABASE_URL', '')
    SUPABASE_ANON_KEY   = os.environ.get('SUPABASE_ANON_KEY', '')
    SUPABASE_SERVICE_KEY= os.environ.get('SUPABASE_SERVICE_KEY', '')

    # Groq AI
    GROQ_API_KEY        = os.environ.get('GROQ_API_KEY', '')

    # Flask-Mail
    MAIL_SERVER         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT           = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS        = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME       = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')

    # APScheduler
    SCHEDULER_API_ENABLED = False
    SCHEDULER_ENABLED     = os.environ.get('SCHEDULER_ENABLED', 'True') == 'True'

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
import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))


class Config:
    SECRET_KEY = os.environ['SECRET_KEY']

    DB_USER = os.environ['DB_USER']
    DB_PASSWORD = os.environ['DB_PASSWORD']
    DB_DSN = os.environ['DB_DSN']
    ORACLE_CLIENT_LIB_DIR = os.environ['ORACLE_CLIENT_LIB_DIR']

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    FEEDBACK_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'feedback')
    PAYMENT_PROOF_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'payment_proofs')
    MAX_CONTENT_LENGTH = 60 * 1024 * 1024  # 60MB hard cap (largest allowed is a single video)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('FORCE_HTTPS', 'false').lower() == 'true'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USER = os.environ['EMAIL_USER']
    EMAIL_PASSWORD = os.environ['EMAIL_PASSWORD']

    CONTACT_PHONE = os.environ.get('CONTACT_PHONE', '')
    CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', '')
    WHATSAPP_NUMBER = os.environ.get('WHATSAPP_NUMBER', '')

    DEBUG = False


class DevConfig(Config):
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'


class ProdConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


def get_config():
    return ProdConfig if os.environ.get('APP_ENV') == 'production' else DevConfig

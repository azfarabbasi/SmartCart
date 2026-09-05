import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

_ON_VERCEL = bool(os.environ.get('VERCEL'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'b96f3e2a1c8d4f7e9a0b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f')

    DB_USER = os.environ.get('DB_USER', 'smart_cart')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'smartcart123')
    DB_DSN = os.environ.get('DB_DSN', 'localhost:1521/XE')
    ORACLE_CLIENT_LIB_DIR = os.environ.get('ORACLE_CLIENT_LIB_DIR')

    UPLOAD_FOLDER = os.path.join('/tmp', 'uploads') if _ON_VERCEL else os.path.join(BASE_DIR, 'static', 'uploads')
    FEEDBACK_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'feedback')
    PAYMENT_PROOF_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'payment_proofs')
    MAX_CONTENT_LENGTH = 60 * 1024 * 1024  # 60MB hard cap (largest allowed is a single video)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('FORCE_HTTPS', 'false').lower() == 'true'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)

    # CSRF Settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # Tokens remain valid for the full session lifetime
    WTF_CSRF_SSL_STRICT = False  # Avoid referrer scheme mismatches behind Vercel edge reverse proxy

    # How long a login lasts. The identity token is stateless, so there is no
    # server-side record to revoke -- keep this short enough that a leaked
    # token stops working, long enough that shoppers aren't logged out mid-visit.
    JWT_LIFETIME = timedelta(days=int(os.environ.get('JWT_LIFETIME_DAYS', 7)))

    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USER = os.environ.get('EMAIL_USER', '')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')

    # Email API Services - preferred for Vercel (no SMTP port restrictions)
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
    RESEND_FROM_EMAIL = os.environ.get('RESEND_FROM_EMAIL', 'SmartCart <onboarding@resend.dev>')

    BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
    BREVO_SENDER_EMAIL = os.environ.get('BREVO_SENDER_EMAIL', os.environ.get('EMAIL_USER', ''))
    BREVO_SENDER_NAME = os.environ.get('BREVO_SENDER_NAME', 'SmartCart')

    CONTACT_PHONE = os.environ.get('CONTACT_PHONE', '')
    CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', '')
    WHATSAPP_NUMBER = os.environ.get('WHATSAPP_NUMBER', '')

    DEBUG = False


class DevConfig(Config):
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'


class ProdConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

    @classmethod
    def validate_production_secrets(cls):
        insecure_defaults = {
            'change-me-generate-with-python-secrets-token-hex-32',
            'dev-secret',
            'secret',
            '123456',
        }
        key = (cls.SECRET_KEY or '').strip()
        if not key or key in insecure_defaults or len(key) < 16:
            import logging
            logging.getLogger(__name__).warning(
                "SECURITY WARNING: Insecure or default SECRET_KEY configured in production. "
                "Please set a strong, random SECRET_KEY in your production environment variables."
            )
            if os.environ.get('STRICT_SECRET_CHECK') == 'true':
                raise RuntimeError(
                    "CRITICAL SECURITY ERROR: Insecure or default SECRET_KEY configured in production."
                )


def get_config():
    if os.environ.get('APP_ENV') == 'production':
        ProdConfig.validate_production_secrets()
        return ProdConfig
    return DevConfig

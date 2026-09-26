# config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # --- Flask Core ---
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(64).hex())
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    ENV = os.getenv("FLASK_ENV", "production")

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'database', 'authshield.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "connect_args": {"check_same_thread": False, "timeout": 30},
    }

    # --- Session & Cookies ---
    SESSION_COOKIE_NAME = "as360_flask_session"
    AUTH_COOKIE_NAME = "as360_auth_sid"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=10)
    PENDING_SESSION_LIFETIME = timedelta(minutes=10)

    # --- OTP Settings ---
    OTP_LENGTH = 6
    OTP_MOBILE_VALID_SECONDS = 60
    OTP_EMAIL_VALID_SECONDS = 60
    OTP_MAX_ATTEMPTS = 5
    OTP_RESEND_COOLDOWN = 60
    OTP_MAX_RESENDS = 3

    # --- Lockout Settings ---
    LOCKOUT_THRESHOLD = 5
    LOCKOUT_MINUTES = 2

    # --- Rate Limiting ---
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_LOGIN = "10 per minute;50 per hour"
    RATELIMIT_OTP_SEND = "3 per 5 minutes"
    RATELIMIT_OTP_VERIFY = "10 per 5 minutes"
    RATELIMIT_DEFAULT = "200 per minute"

    # --- Admin IP Whitelist ---
    ADMIN_IP_WHITELIST = [
        ip.strip() for ip in os.getenv("ADMIN_IP_WHITELIST", "127.0.0.1,::1").split(",") if ip.strip()
    ]
    TRUST_PROXY = os.getenv("TRUST_PROXY", "false").lower() == "true"

    # --- WhatsApp Cloud API ---
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")

    # --- Email SMTP ---
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

    # --- OTP Delivery Targets ---
    TEST_MOBILE = os.getenv("TEST_MOBILE", "+923175302914")
    TEST_EMAIL = os.getenv("TEST_EMAIL", "azanawankhan222@gmail.com")

    # --- Dev Mode ---
    DEV_MODE_PRINT_OTP = os.getenv("DEV_MODE_PRINT_OTP", "false").lower() == "true"
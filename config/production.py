import os

from .settings import *  # noqa: F401,F403


DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

ALLOWED_HOSTS = [
    item.strip()
    for item in os.environ.get(
        "ALLOWED_HOSTS",
        "panel.kimiagarkhoone.com,109.122.250.125,127.0.0.1",
    ).split(",")
    if item.strip()
]

CSRF_TRUSTED_ORIGINS = [
    item.strip()
    for item in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        "https://panel.kimiagarkhoone.com",
    ).split(",")
    if item.strip()
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "kimiagar_db"),
        "USER": os.environ.get("DB_USER", "kimiagar_user"),
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

TEMPLATES[0]["OPTIONS"]["debug"] = False

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WORKER_URL = os.environ.get("TELEGRAM_WORKER_URL", "")
KAVENEGAR_API_KEY = os.environ.get("KAVENEGAR_API_KEY", "")
KAVENEGAR_SENDER = os.environ.get("KAVENEGAR_SENDER", "")

USE_HTTPS = os.environ.get("USE_HTTPS", "0") == "1"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = USE_HTTPS
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

"""
Django settings for the Rashal Energies Compliance Management System.

Configuration is driven by a .env file in the project root.
Copy .env.example to .env and edit it before running.
"""

from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def env_list(key, default=""):
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = env("SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Local
    "core",
    "accounts",
    "stations",
    "compliance",
    "alerts",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# Django's stock CSRF page explains cross-site attack vectors to someone who
# just wants to log in. Almost every real hit is a stale token: a tab left
# open across a restart, a rebuild, or a login in another tab. Say that
# instead, and give them the reload button.
CSRF_FAILURE_VIEW = "core.views.csrf_failure"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Defaults to SQLite so the project runs immediately after clone.
# Set DB_ENGINE=postgres in .env to use PostgreSQL.

if env("DB_ENGINE", "sqlite") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "rashal_compliance"),
            "USER": env("DB_USER", "postgres"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "127.0.0.1"),
            "PORT": env("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"


# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Dar_es_Salaam"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static and media
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Compliance documents are PRIVATE. MEDIA_URL is deliberately not served.
# Every file is streamed through compliance.views.serve_document, which
# checks the user's station scope first. Do not add a media route to urls.py
# and do not point nginx at MEDIA_ROOT.
MEDIA_ROOT = BASE_DIR / "private_media"
MEDIA_URL = None

FILE_UPLOAD_PERMISSIONS = 0o600
MAX_UPLOAD_BYTES = int(env("MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
ALLOWED_UPLOAD_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

if env("EMAIL_BACKEND"):
    EMAIL_BACKEND = env("EMAIL_BACKEND")
else:
    EMAIL_BACKEND = (
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    )

EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", 587))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "compliance@rashal.co.tz")


# ---------------------------------------------------------------------------
# SMS (Beem Africa)
# ---------------------------------------------------------------------------
# SMS_BACKEND: "log" writes messages to the console/log instead of sending.
# Keep it on "log" everywhere except production.

SMS_BACKEND = env("SMS_BACKEND", "log")  # "log" | "beem"
BEEM_API_KEY = env("BEEM_API_KEY", "")
BEEM_SECRET_KEY = env("BEEM_SECRET_KEY", "")
BEEM_SENDER_ID = env("BEEM_SENDER_ID", "INFO")
BEEM_SEND_URL = env("BEEM_SEND_URL", "https://apisms.beem.africa/v1/send")
SMS_DEFAULT_COUNTRY_CODE = env("SMS_DEFAULT_COUNTRY_CODE", "255")


# ---------------------------------------------------------------------------
# Compliance domain settings
# ---------------------------------------------------------------------------

SITE_BASE_URL = env("SITE_BASE_URL", "http://127.0.0.1:8000")

BRAND = {
    "company_name": env("COMPANY_NAME", "Rashal Energies"),
    "tagline": env("COMPANY_TAGLINE", "Igniting Africa"),
}

# Urgency bands, in days remaining. See core.bands.band_for().
BAND_CRITICAL_DAYS = 90
BAND_WARNING_DAYS = 180
BAND_ACTIVE_DAYS = 365

# Rungs that repeat every day until resolved, rather than firing once.
REPEATING_ALERT_THRESHOLDS = [7, 0]


# ---------------------------------------------------------------------------
# Security (production)
# ---------------------------------------------------------------------------

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "alerts": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "compliance": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
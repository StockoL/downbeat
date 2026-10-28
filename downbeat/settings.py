"""Settings for Downbeat. One user, one laptop, SQLite."""

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Per-install files that never leave the laptop: the secret key, logs.
LOCAL_DIR = Path(os.environ.get("DOWNBEAT_LOCAL_DIR", BASE_DIR / "local"))
LOCAL_DIR.mkdir(exist_ok=True)


def _secret_key():
    """From the environment, or generated once per install and kept in local/."""
    if os.environ.get("DOWNBEAT_SECRET_KEY"):
        return os.environ["DOWNBEAT_SECRET_KEY"]
    path = LOCAL_DIR / "secret_key"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(50), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


SECRET_KEY = _secret_key()
# Off unless asked for: set DOWNBEAT_DEBUG=1 while developing.
DEBUG = os.environ.get("DOWNBEAT_DEBUG") == "1"

# The laptop's Tailscale name(s), e.g. "teacher-laptop.tail1234.ts.net". Tailscale's own HTTPS
# proxy (`tailscale serve`) terminates TLS with a real certificate and forwards to localhost.
# Written by tools/tailscale-check.ps1 into local/hosts.txt, or given in DOWNBEAT_HOSTS.
_hosts_file = LOCAL_DIR / "hosts.txt"
_hosts = os.environ.get("DOWNBEAT_HOSTS") or (_hosts_file.read_text(encoding="utf-8-sig") if _hosts_file.exists() else "")
TAILNET_HOSTS = [h.strip() for h in _hosts.replace("\n", ",").split(",") if h.strip()]
ALLOWED_HOSTS = ["127.0.0.1", "localhost", *TAILNET_HOSTS]
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in TAILNET_HOSTS]
if TAILNET_HOSTS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # browsers only honour it over HTTPS, so localhost is unaffected

# No HTTPS redirect: the laptop itself uses http://127.0.0.1, which never leaves the machine;
# every other device arrives through Tailscale's HTTPS.
# HSTS preload and subdomains are for public domains; a private ts.net name never joins the preload list.
SILENCED_SYSTEM_CHECKS = ["security.W008", "security.W005", "security.W021"]

# One teacher, two devices: stay signed in for a term so the iPad never asks mid-lesson.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 120
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "today"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.forms",
    "django_looseleaf",
    "core",
    "timetable",
    "rooms",
    "notes",
    "pupils",
    "plans",
    "assessment",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.GateMiddleware",
]

ROOT_URLCONF = "downbeat.urls"

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
            ],
        },
    },
]

FORM_RENDERER = "django_looseleaf.renderers.LooseLeafFormRenderer"
LOOSELEAF_THEME = "theme"

WSGI_APPLICATION = "downbeat.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DOWNBEAT_DB", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {
            # WAL lets a backup or a second tab read while a write is in progress; IMMEDIATE
            # transactions plus a timeout make overlapping writes wait their turn instead of failing.
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;",
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
        },
    }
}

# Where `manage.py backup` writes, e.g. a OneDrive folder. Defaults to backups/ beside the code.
BACKUP_DIR = Path(os.environ.get("DOWNBEAT_BACKUP_DIR", BASE_DIR / "backups"))
BACKUP_KEEP = int(os.environ.get("DOWNBEAT_BACKUP_KEEP", "30"))

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_ROOT.mkdir(exist_ok=True)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
# Serve straight from the app folders too, so the app works whether or not collectstatic has run.
WHITENOISE_USE_FINDERS = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

(LOCAL_DIR / "logs").mkdir(exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOCAL_DIR / "logs" / "downbeat.log",
            "maxBytes": 1_000_000,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "plain",
            "level": "WARNING",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {"django.server": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}

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
DEBUG = os.environ.get("DOWNBEAT_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
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
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.FirstRunMiddleware",
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

"""Base Django settings — shared by every environment.

Environment-specific values come from environment variables via
:mod:`nazbeen_forex_ai.config`. See ``.env.example`` for the full list.
"""

from __future__ import annotations

from pathlib import Path

from nazbeen_forex_ai import __version__
from nazbeen_forex_ai.config import env_bool, env_int, env_list, env_str, load_dotenv

# Load local .env (git-ignored) before reading any configuration.
load_dotenv()

# BASE_DIR = repository root (nazbeen_forex_ai/ is one level below it).
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Core -----------------------------------------------------------------

# Development-only fallback; production settings refuse to start without a real key.
SECRET_KEY = env_str("DJANGO_SECRET_KEY", "insecure-development-only-key-do-not-use-in-prod")

DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS: list[str] = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

APP_VERSION = env_str("APP_VERSION", __version__) or __version__

# --- Applications ---------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "channels",
    # Project apps
    "nazbeen_forex_ai.core",
    "nazbeen_forex_ai.accounts",
    "nazbeen_forex_ai.marketdata",
    "nazbeen_forex_ai.structure",
    "nazbeen_forex_ai.analysis",
    "nazbeen_forex_ai.risk",
    "nazbeen_forex_ai.backtesting",
    "nazbeen_forex_ai.journal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "nazbeen_forex_ai.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "nazbeen_forex_ai.wsgi.application"
ASGI_APPLICATION = "nazbeen_forex_ai.asgi.application"

# --- Database -------------------------------------------------------------

# SQLite by default for development; set DATABASE_URL to use PostgreSQL.
DATABASE_URL = env_str("DATABASE_URL", "")

if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    # parsenetloc-based configuration; credentials come from the environment only.
    from urllib.parse import unquote, urlparse

    _db_parsed = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(_db_parsed.path.lstrip("/")),
            "USER": unquote(_db_parsed.username or ""),
            "PASSWORD": unquote(_db_parsed.password or ""),
            "HOST": _db_parsed.hostname or "",
            "PORT": str(_db_parsed.port or ""),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Cache / Redis ---------------------------------------------------------

# LocMem fallback keeps development runnable without Redis; production/CI should
# set REDIS_URL. The health endpoint reports which backend is active.
REDIS_URL = env_str("REDIS_URL", "")

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "nazbeen-forex-ai",
        }
    }

# --- Celery ---------------------------------------------------------------

CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", REDIS_URL) or ""
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", REDIS_URL) or ""
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_TRACK_STARTED = True
# Named queues (Roadmap Phase 10): heavy work (backtests, evaluations) must not
# starve lightweight tasks. Routing keeps default tasks on "default".
CELERY_TASK_QUEUES = {
    "default": {"exchange": "default", "routing_key": "default"},
    "heavy": {"exchange": "heavy", "routing_key": "heavy"},
}
CELERY_TASK_ROUTES = {
    "nazbeen_forex_ai.backtesting.*": {"queue": "heavy"},
}
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # fairness for long-running backtests

# --- Channels (WebSockets) -------------------------------------------------

ASGI_APPLICATION = "nazbeen_forex_ai.asgi.application"

if env_bool("USE_REDIS_CHANNELS", False):
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels_redis.core.RedisChannelLayer",
                    "CONFIG": {"hosts": [REDIS_URL]}},
    }
else:
    # In-memory layer: development and tests (no external dependency).
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# --- CORS (frontend dev server) -------------------------------------------

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
CORS_ALLOW_CREDENTIALS = False  # token auth, not cookies

# --- Security defaults -----------------------------------------------------

# Upload limits (MASTER_SPEC §4) — screenshots land in a later phase.
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("DATA_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = env_int("FILE_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Localization ---------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"  # Internal representation is always UTC (MASTER_SPEC §3.B).
USE_I18N = True
USE_TZ = True

# --- Static files ---------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- REST framework -------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Secure default: endpoints must opt in to being public.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Resilient throttles: if the cache (Redis) is down they allow the request
    # instead of raising a 500 (ADR-008).
    "DEFAULT_THROTTLE_CLASSES": [
        "nazbeen_forex_ai.core.throttling.ResilientAnonRateThrottle",
        "nazbeen_forex_ai.core.throttling.ResilientUserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env_str("THROTTLE_RATE_ANON", "60/min") or "60/min",
        "user": env_str("THROTTLE_RATE_USER", "600/min") or "600/min",
        "auth": env_str("THROTTLE_RATE_AUTH", "10/min") or "10/min",
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "UNAUTHENTICATED_USER": None,
}

# --- Logging --------------------------------------------------------------

LOG_LEVEL = env_str("LOG_LEVEL", "INFO") or "INFO"
# "text" = key=value lines (default), "json" = one JSON object per line.
LOG_FORMAT = (env_str("LOG_FORMAT", "text") or "text").lower()

_CONSOLE_FORMATTER = "structured" if LOG_FORMAT != "json" else "json"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            # Machine-readable key=value structure.
            "format": (
                "%(asctime)s level=%(levelname)s logger=%(name)s "
                "message=%(message)s"
            ),
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
        },
        "json": {
            "()": "nazbeen_forex_ai.core.logging_extras.JsonFormatter",
        },
    },
    "filters": {
        # Defense-in-depth: mask credentials/token patterns in every record
        # (MASTER_SPEC §7 — never expose API keys or credentials in logs).
        "redact": {"()": "nazbeen_forex_ai.core.logging_extras.SecretRedactionFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": _CONSOLE_FORMATTER,
            "filters": ["redact"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "nazbeen_forex_ai": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

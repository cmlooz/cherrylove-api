"""Settings shared by every environment. Values come only from environment variables (DEC-039).

`django.contrib.auth` arrives with the custom user model (F2.1), so the first auth migration already uses
`identity.User`; the Django Admin arrives in F9.
"""

from __future__ import annotations

from pathlib import Path

from config.settings import env

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = env.required("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env.csv("DJANGO_ALLOWED_HOSTS")

# The only origin allowed by CORS, with credentials (ADR-004 §2).
WEB_ORIGIN = env.required("WEB_ORIGIN")
SECURE_REFERRER_POLICY = "no-referrer"

# HMAC key for failed-login email fingerprints (ADR-008 §2): its own key, never SECRET_KEY or the KEK.
AUDIT_HMAC_KEY = env.required("AUDIT_HMAC_KEY")

# Key-encryption key, base64 of 32 bytes (ADR-009 §1): env or secret manager only, never in the database.
KEK = env.required("KEK")

# Cache and throttles (ADR-011).
REDIS_URL = env.required("REDIS_URL")

# Outgoing email over SMTP (Mailpit locally, REQ-N-OPS-01).
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env.required("EMAIL_HOST")
EMAIL_PORT = env.integer("EMAIL_PORT")
DEFAULT_FROM_EMAIL = env.required("DEFAULT_FROM_EMAIL")
# Where an invite link opens; the route belongs to the web app (plan G). `{token}` is replaced.
INVITE_LINK_TEMPLATE = env.required("INVITE_LINK_TEMPLATE")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "drf_spectacular",
    "django_tasks",
    "django_tasks_db",
    "cherrylove.shared.apps.SharedConfig",
    "cherrylove.audit.apps.AuditConfig",
    "cherrylove.identity.apps.IdentityConfig",
    "cherrylove.sync.apps.SyncConfig",
]

# Custom user from the first identity migration (ADR-004 §4, DATA-001 §3); Argon2 first (argon2-cffi).
AUTH_USER_MODEL = "identity.User"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
]

# ADR-002 §1: migrations live in each module's infrastructure layer.
MIGRATION_MODULES = {
    "shared": "cherrylove.shared.infrastructure.migrations",
    "audit": "cherrylove.audit.infrastructure.migrations",
    "identity": "cherrylove.identity.infrastructure.migrations",
    "sync": "cherrylove.sync.infrastructure.migrations",
}

MIDDLEWARE = [
    "cherrylove.shared.interfaces.http.middleware.request_id.RequestIdMiddleware",
    "cherrylove.shared.interfaces.http.middleware.cors.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "cherrylove.shared.interfaces.http.middleware.security_headers.SecurityHeadersMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
WSGI_APPLICATION = "config.wsgi.application"
APPEND_SLASH = False

# Two roles on one database (ADR-008 §4, DATA-001 §3): the app role has DML only; every
# migration runs on the `maintenance` alias (`manage.py migrate --database maintenance`).
_DATABASE = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": env.required("DB_NAME"),
    "HOST": env.required("DB_HOST"),
    "PORT": env.integer("DB_PORT"),
}
DATABASES = {
    "default": {
        **_DATABASE,
        "USER": env.required("DB_USER"),
        "PASSWORD": env.required("DB_PASSWORD"),
    },
    "maintenance": {
        **_DATABASE,
        "USER": env.required("DB_MAINTENANCE_USER"),
        "PASSWORD": env.required("DB_MAINTENANCE_PASSWORD"),
    },
}
DATABASE_ROUTERS = ["config.db_routers.MaintenanceMigrationsRouter"]

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# DRF without django.contrib.auth until F2.1: no session auth, no AnonymousUser model import.
REST_FRAMEWORK: dict[str, object] = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "cherrylove.shared.interfaces.http.problem_details.exception_handler",
}

# Generated schema must match contract/openapi.v1.yaml (ADR-003 §2, DEC-048).
SPECTACULAR_SETTINGS: dict[str, object] = {
    "OAS_VERSION": "3.1.0",
    "TITLE": "CherryLove API",
    "VERSION": "1.0.0",
    "SERVERS": [{"url": "/api/v1"}],
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "SCHEMA_PATH_PREFIX_TRIM": True,
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {},  # filled as contract enums (Language, SyncEntityType, ...) get implemented
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "cherrylove.shared.interfaces.http.openapi.enforce_operation_ids",
    ],
}

# JSON lines to stdout with the request ID (ADR-008 §7, REQ-N-QA-01). Never content.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "cherrylove.shared.infrastructure.logging.RequestIdFilter"}},
    "formatters": {"json": {"()": "cherrylove.shared.infrastructure.logging.JsonFormatter"}},
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "filters": ["request_id"],
            "formatter": "json",
        }
    },
    "root": {"handlers": ["stdout"], "level": "INFO"},
}

# Jobs on PostgreSQL, two queues and two workers (ADR-013 §1): Redis is not a broker.
TASKS = {
    "default": {
        "BACKEND": "django_tasks_db.DatabaseBackend",
        "QUEUES": ["default", "media"],
    }
}

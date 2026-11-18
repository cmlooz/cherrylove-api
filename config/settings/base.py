"""Settings shared by every environment. Values come only from environment variables (DEC-039).

INSTALLED_APPS has no `django.contrib.auth` / `admin` until F2.1 (IMPL-API-001 F0), so no auth table
exists before the custom user model.
"""

from __future__ import annotations

from pathlib import Path

from config.settings import env

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = env.required("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env.csv("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "rest_framework",
    "drf_spectacular",
    "cherrylove.shared.apps.SharedConfig",
]

# ADR-002 §1: migrations live in each module's infrastructure layer.
MIGRATION_MODULES = {"shared": "cherrylove.shared.infrastructure.migrations"}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
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
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# Generated schema must match contract/openapi.v1.yaml (ADR-003 §2, DEC-048).
SPECTACULAR_SETTINGS = {
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

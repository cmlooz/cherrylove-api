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

INSTALLED_APPS: list[str] = []

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
APPEND_SLASH = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.required("DB_NAME"),
        "USER": env.required("DB_USER"),
        "PASSWORD": env.required("DB_PASSWORD"),
        "HOST": env.required("DB_HOST"),
        "PORT": env.integer("DB_PORT"),
    }
}

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

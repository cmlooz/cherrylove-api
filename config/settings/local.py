"""Local development: defaults that match compose.yaml; any real environment variable wins."""

from __future__ import annotations

import os

for _name, _value in {
    "DJANGO_SECRET_KEY": "local-only-not-a-secret-local-only-not-a-secret-0001",
    "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
    "DB_NAME": "cherrylove",
    "DB_USER": "postgres",
    "DB_PASSWORD": "postgres",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "5432",
}.items():
    os.environ.setdefault(_name, _value)

from config.settings.base import *  # noqa: E402, F403

DEBUG = True

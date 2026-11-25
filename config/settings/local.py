"""Local development: defaults that match compose.yaml; any real environment variable wins."""

from __future__ import annotations

import os

for _name, _value in {
    "DJANGO_SECRET_KEY": "local-only-not-a-secret-local-only-not-a-secret-0001",
    "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
    "WEB_ORIGIN": "http://localhost:5173",
    "AUDIT_HMAC_KEY": "local-only-audit-hmac-not-a-secret-0001",
    "KEK": "bG9jYWwtb25seS1rZWstbm90LWEtc2VjcmV0LTAwMDE=",  # 32 bytes, local data only
    "DB_NAME": "cherrylove",
    "DB_USER": "cherrylove_app",
    "DB_PASSWORD": "local-app",
    "DB_MAINTENANCE_USER": "cherrylove_maintenance",
    "DB_MAINTENANCE_PASSWORD": "local-maintenance",
    "REDIS_URL": "redis://127.0.0.1:6379/0",
    "EMAIL_HOST": "127.0.0.1",
    "EMAIL_PORT": "1025",
    "DEFAULT_FROM_EMAIL": "CherryLove <noreply@cherrylove.local>",
    "INVITE_LINK_TEMPLATE": "http://localhost:5173/invites/{token}",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "5432",
}.items():
    os.environ.setdefault(_name, _value)

from config.settings.base import *  # noqa: E402, F403

DEBUG = True

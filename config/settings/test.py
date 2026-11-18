"""Test settings: local defaults, real PostgreSQL (ADR-014 §1, never SQLite)."""

from __future__ import annotations

from config.settings.local import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

"""Test settings: local defaults, real PostgreSQL (ADR-014 §1, never SQLite)."""

from __future__ import annotations

from config.settings.local import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

# Test-only app with a couple-owned probe model for the fail-closed manager (F1.6).
INSTALLED_APPS = [*INSTALLED_APPS, "tests.apps.scoping"]  # noqa: F405

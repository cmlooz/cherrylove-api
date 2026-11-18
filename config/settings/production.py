"""Production settings: everything from the environment, hardened for `check --deploy`."""

from __future__ import annotations

from config.settings.base import *  # noqa: F403

SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]  # container probes call it over plain HTTP
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
CSRF_COOKIE_SECURE = True

# HSTS preload is a commitment of the production domain, decided with the production ADR (DEC-022).
SILENCED_SYSTEM_CHECKS = ["security.W021"]

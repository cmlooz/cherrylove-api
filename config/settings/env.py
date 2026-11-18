"""Typed readers for environment variables: the only source of configuration (DEC-039, 12-factor)."""

from __future__ import annotations

import os

from django.core.exceptions import ImproperlyConfigured


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Environment variable {name} is required.")
    return value


def integer(name: str) -> int:
    value = required(name)
    if not value.isdigit():
        raise ImproperlyConfigured(f"Environment variable {name} must be an integer.")
    return int(value)


def csv(name: str) -> list[str]:
    return [item.strip() for item in required(name).split(",") if item.strip()]

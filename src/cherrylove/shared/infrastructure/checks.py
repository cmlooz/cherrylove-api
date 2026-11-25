"""Startup checks for secrets (DEC-039, ADR-008 §2): wrong keys stop the process before it serves anything."""

from __future__ import annotations

import base64
import binascii
from typing import Any

from django.conf import settings
from django.core.checks import CheckMessage, Error, register


@register()
def audit_hmac_key_is_its_own(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    key = getattr(settings, "AUDIT_HMAC_KEY", "")
    others = {"SECRET_KEY": settings.SECRET_KEY, "KEK": getattr(settings, "KEK", None)}
    if not key:
        return [Error("AUDIT_HMAC_KEY is empty.", id="cherrylove.E001")]
    return [
        Error(f"AUDIT_HMAC_KEY must differ from {name}.", id="cherrylove.E002")
        for name, value in others.items()
        if value and value == key
    ]


@register()
def kek_is_256_bits(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    value = getattr(settings, "KEK", "")
    try:
        decoded = base64.b64decode(value, validate=True)
    except binascii.Error, ValueError:
        decoded = b""
    if len(decoded) != 32:
        return [Error("KEK must be the base64 encoding of exactly 32 bytes (ADR-009 §1).", id="cherrylove.E003")]
    return []


@register()
def jwt_signing_key_is_its_own(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    key = getattr(settings, "JWT_SIGNING_KEY", "")
    if not key:
        return [Error("JWT_SIGNING_KEY is empty.", id="cherrylove.E004")]
    others = {
        "SECRET_KEY": settings.SECRET_KEY,
        "KEK": getattr(settings, "KEK", None),
        "AUDIT_HMAC_KEY": getattr(settings, "AUDIT_HMAC_KEY", None),
    }
    return [
        Error(f"JWT_SIGNING_KEY must differ from {name} (ADR-004 §1).", id="cherrylove.E005")
        for name, value in others.items()
        if value and value == key
    ]

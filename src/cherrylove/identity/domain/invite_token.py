"""Invite tokens (ADR-004 §4): 32 random bytes, single use, stored only as their SHA-256."""

from __future__ import annotations

import hashlib

TOKEN_BYTES = 32


def hash_token(raw: str) -> bytes:
    return hashlib.sha256(raw.encode()).digest()

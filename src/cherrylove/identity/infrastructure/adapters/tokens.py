"""Random invite tokens (ADR-004 §4): `secrets`, 32 bytes, URL-safe."""

from __future__ import annotations

import secrets

from cherrylove.identity.domain.invite_token import TOKEN_BYTES


class SecretsTokenGenerator:
    def new(self) -> str:
        return secrets.token_urlsafe(TOKEN_BYTES)

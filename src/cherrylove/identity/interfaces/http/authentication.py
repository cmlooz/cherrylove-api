"""Bearer access-token authentication (ADR-004 §1) and its OpenAPI name `bearerAuth` (API-001)."""

from __future__ import annotations

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework_simplejwt.authentication import JWTAuthentication


class PartnerJWTAuthentication(JWTAuthentication):
    """Validates the minimal access token (AUTH_TOKEN_CLASSES); the Actor is resolved in F2.14."""


class PartnerJWTAuthenticationScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "cherrylove.identity.interfaces.http.authentication.PartnerJWTAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}

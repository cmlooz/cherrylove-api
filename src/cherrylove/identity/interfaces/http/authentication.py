"""Bearer access-token authentication (ADR-004 §1) and its OpenAPI name `bearerAuth` (API-001).

SimpleJWT verifies the minimal access token; instead of loading the ORM user, the subject is turned into the
Actor by the cached resolver (ADR-005 §1, F2.14). A user who is no longer a partner of an active couple gets
`401 not_authenticated` even with a valid access token.
"""

from __future__ import annotations

import uuid
from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import Token

from cherrylove.identity import wiring
from cherrylove.shared.domain.errors import NotAuthenticated
from cherrylove.shared.domain.ids import UserId
from cherrylove.shared.interfaces.http.actor import Partner


class PartnerJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token: Token) -> Any:
        subject = validated_token.get(api_settings.USER_ID_CLAIM)
        if not subject:
            raise NotAuthenticated("the token has no subject")
        actor = wiring.actor_resolver().resolve(UserId(uuid.UUID(str(subject))))
        session = validated_token.get("sid")
        return Partner(actor, session_id=str(session) if session else None)


class PartnerJWTAuthenticationScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "cherrylove.identity.interfaces.http.authentication.PartnerJWTAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}

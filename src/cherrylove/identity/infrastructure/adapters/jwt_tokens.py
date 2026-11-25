"""JWT sessions on SimpleJWT (ADR-004 §1-3); the library lives only here.

Access tokens carry exactly `sub`, `exp`, `iat` and `jti` (no couple claim: ADR-005 resolves it server-side).
Without a type claim a 30-day refresh token would also pass as an access token, so the rule is inverted: the
refresh token keeps its `token_type`, and access verification refuses any token that has one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from cherrylove.identity.application.ports import Session
from cherrylove.identity.infrastructure.orm import User
from cherrylove.shared.domain.ids import UserId


class MinimalAccessToken(AccessToken):
    def __init__(self, token: Any = None, verify: bool = True) -> None:
        super().__init__(token, verify)
        if token is None:
            self.payload.pop(api_settings.TOKEN_TYPE_CLAIM, None)

    def verify_token_type(self) -> None:
        if api_settings.TOKEN_TYPE_CLAIM in self.payload:
            raise TokenError("not an access token")


class PartnerRefreshToken(RefreshToken):
    access_token_class = MinimalAccessToken


def _expiry(token: AccessToken | RefreshToken) -> datetime:
    return datetime.fromtimestamp(int(token["exp"]), tz=UTC)


class JwtTokenIssuer:
    def issue(self, user_id: UserId) -> Session:
        """A new session: refresh registered as outstanding (rotation and blacklist, ADR-004 §3)."""
        refresh = PartnerRefreshToken.for_user(User.objects.get(id=user_id.value))
        access = refresh.access_token
        return Session(str(access), _expiry(access), str(refresh), _expiry(refresh))

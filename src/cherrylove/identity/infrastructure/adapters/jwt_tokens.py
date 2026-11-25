"""JWT sessions on SimpleJWT (ADR-004 §1-3); the library lives only here.

Access tokens carry exactly `sub`, `exp`, `iat` and `jti` (no couple claim: ADR-005 resolves it server-side).
Without a type claim a 30-day refresh token would also pass as an access token, so the rule is inverted: the
refresh token keeps its `token_type`, and access verification refuses any token that has one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from rest_framework_simplejwt.exceptions import TokenBackendError, TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from cherrylove.identity.application.ports import RefreshCheck, Session
from cherrylove.identity.infrastructure.orm import Couple, User
from cherrylove.shared.domain.errors import NotAuthenticated
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


def _partner(user_id: object) -> User | None:
    """An active partner of an active couple: anyone else loses refresh rights (ADR-004 §3, REQ-F-AUTH-09)."""
    return (
        User.objects.filter(
            id=str(user_id),
            is_active=True,
            is_staff=False,
            membership__couple__status=Couple.Status.ACTIVE,
        )
        .select_related("membership")
        .first()
    )


def _encoded(refresh: str) -> Any:
    """SimpleJWT's hints say `Token | None`, but its constructor takes the encoded string (documented API)."""
    return refresh


class JwtSessionStore:
    """Rotation and revocation on SimpleJWT's outstanding/blacklisted tables; library errors become port errors."""

    def check(self, refresh: str) -> RefreshCheck:
        # Verify signature and expiry only: the token constructor would also refuse a blacklisted token,
        # and that is exactly the case to tell apart (a reused copy) from a forged or expired one.
        try:
            payload = token_backend.decode(_encoded(refresh), verify=True)
        except TokenBackendError:
            return RefreshCheck("invalid")
        if payload.get(api_settings.TOKEN_TYPE_CLAIM) != PartnerRefreshToken.token_type or not payload.get("jti"):
            return RefreshCheck("invalid")
        user_id = UserId(uuid.UUID(str(payload["sub"])))
        if BlacklistedToken.objects.filter(token__jti=payload["jti"]).exists():
            return RefreshCheck("reused", user_id)
        return RefreshCheck("valid", user_id)

    def revoke_all(self, user_id: UserId) -> int:
        live = OutstandingToken.objects.filter(user_id=user_id.value, blacklistedtoken__isnull=True)
        tokens = list(live)
        BlacklistedToken.objects.bulk_create([BlacklistedToken(token=token) for token in tokens])
        return len(tokens)

    def rotate(self, refresh: str) -> tuple[UserId, Session]:
        try:
            token = PartnerRefreshToken(_encoded(refresh))
            token.check_blacklist()
        except TokenError:
            raise NotAuthenticated("unusable refresh token") from None
        user = _partner(token["sub"])
        if user is None:
            raise NotAuthenticated("the account can no longer refresh")
        token.blacklist()
        return UserId(user.id), JwtTokenIssuer().issue(UserId(user.id))

    def revoke(self, refresh: str) -> UserId | None:
        try:
            token = PartnerRefreshToken(_encoded(refresh))
            token.check_blacklist()
        except TokenError:
            return None
        token.blacklist()
        return UserId(uuid.UUID(str(token["sub"])))

"""JWT sessions on SimpleJWT (ADR-004 §1-3); the library lives only here.

Access tokens carry exactly `sub`, `exp`, `iat`, `jti` and `sid` (no couple claim: ADR-005 resolves it
server-side). `sid` names the session: the `jti` of its first refresh token, kept by every rotation, so a
password change can keep the current session and revoke the others (DEC-051).

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


SESSION_CLAIM = "sid"


def _session(user: User, sid: str | None = None) -> Session:
    """A refresh registered as outstanding (rotation and blacklist, ADR-004 §3) in session `sid` (new if None).

    `for_user` stores the encoded token before `sid` is set, so the stored copy is replaced: revoking the other
    sessions reads `sid` from it.
    """
    refresh = PartnerRefreshToken.for_user(user)
    refresh[SESSION_CLAIM] = sid or str(refresh["jti"])
    OutstandingToken.objects.filter(jti=refresh["jti"]).update(token=str(refresh))
    access = refresh.access_token  # copies `sid`
    return Session(str(access), _expiry(access), str(refresh), _expiry(refresh))


class JwtTokenIssuer:
    def issue(self, user_id: UserId) -> Session:
        """A new session."""
        return _session(User.objects.get(id=user_id.value))


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


def _stored_session(token: OutstandingToken) -> object:
    """`sid` of a stored refresh token; our own tokens, so the signature was checked when they were issued."""
    return token_backend.decode(_encoded(token.token), verify=False).get(SESSION_CLAIM)


def _was_rotated(jti: str, sid: object) -> bool:
    """A blacklisted refresh is a stolen copy only if its session went on with a newer token (ADR-004 §3).

    A token revoked by logout, password change or deactivation is the newest of its session: presenting it
    again is a device that missed the news, not a theft, so it must not kill the other sessions.
    """
    if not sid:
        return True  # no session to follow: treat every blacklisted copy as reuse (conservative)
    stored = OutstandingToken.objects.filter(jti=jti).only("id", "user_id").first()
    if stored is None or stored.user_id is None:
        return False
    newer = OutstandingToken.objects.filter(user_id=stored.user_id, id__gt=stored.id).only("token")
    return any(_stored_session(token) == sid for token in newer)


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
            rotated = _was_rotated(str(payload["jti"]), payload.get(SESSION_CLAIM))
            return RefreshCheck("reused" if rotated else "invalid", user_id)
        return RefreshCheck("valid", user_id)

    def revoke_all(self, user_id: UserId) -> int:
        live = OutstandingToken.objects.filter(user_id=user_id.value, blacklistedtoken__isnull=True)
        tokens = list(live)
        BlacklistedToken.objects.bulk_create([BlacklistedToken(token=token) for token in tokens])
        return len(tokens)

    def revoke_others(self, user_id: UserId, keep_session: str) -> int:
        live = OutstandingToken.objects.filter(user_id=user_id.value, blacklistedtoken__isnull=True)
        others = [token for token in live if _stored_session(token) != keep_session]
        BlacklistedToken.objects.bulk_create([BlacklistedToken(token=token) for token in others])
        return len(others)

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
        return UserId(user.id), _session(user, token.get(SESSION_CLAIM))

    def revoke(self, refresh: str) -> UserId | None:
        try:
            token = PartnerRefreshToken(_encoded(refresh))
            token.check_blacklist()
        except TokenError:
            return None
        token.blacklist()
        return UserId(uuid.UUID(str(token["sub"])))

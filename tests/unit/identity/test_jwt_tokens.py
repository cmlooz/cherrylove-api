"""JWT issuer claims and lifetimes (IMPL-API-001 F2.9; ADR-004 §1, REQ-N-SEC-01)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import jwt
import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from cherrylove.identity.infrastructure.adapters.jwt_tokens import MinimalAccessToken, PartnerRefreshToken
from cherrylove.shared.infrastructure.checks import jwt_signing_key_is_its_own


def _pair() -> tuple[AccessToken, PartnerRefreshToken]:
    refresh = PartnerRefreshToken()
    refresh["sub"] = str(uuid.uuid7())
    return refresh.access_token, refresh


def _claims(token: object) -> dict[str, object]:
    decoded: dict[str, object] = jwt.decode(str(token), settings.JWT_SIGNING_KEY, algorithms=["HS256"])
    return decoded


@pytest.mark.req("REQ-N-SEC-01")
def test_access_token_has_only_sub_exp_iat_jti_and_lives_10_minutes() -> None:
    access, _ = _pair()
    claims = _claims(access)
    assert set(claims) == {"sub", "exp", "iat", "jti"}
    assert "couple_id" not in claims
    assert int(str(claims["exp"])) - int(str(claims["iat"])) == timedelta(minutes=10).total_seconds()


@pytest.mark.req("REQ-N-SEC-01")
def test_refresh_token_lives_30_days_and_keeps_its_type() -> None:
    _, refresh = _pair()
    claims = _claims(refresh)
    assert claims["token_type"] == "refresh"
    assert int(str(claims["exp"])) - int(str(claims["iat"])) == timedelta(days=30).total_seconds()


@pytest.mark.req("REQ-N-SEC-01")
def test_tokens_are_hs256_signed_with_a_key_other_than_secret_key() -> None:
    access, _ = _pair()
    assert jwt.get_unverified_header(str(access))["alg"] == "HS256"
    assert settings.JWT_SIGNING_KEY != settings.SECRET_KEY
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(str(access), settings.SECRET_KEY, algorithms=["HS256"])


@pytest.mark.req("REQ-N-SEC-01")
def test_a_refresh_token_is_never_accepted_as_an_access_token() -> None:
    access, refresh = _pair()
    assert MinimalAccessToken(str(access))["sub"] == _claims(access)["sub"]
    with pytest.raises(TokenError):
        MinimalAccessToken(str(refresh))


@pytest.mark.req("REQ-N-SEC-01")
@pytest.mark.parametrize("other", ["SECRET_KEY", "KEK", "AUDIT_HMAC_KEY"])
def test_startup_check_refuses_a_shared_signing_key(other: str) -> None:
    with override_settings(JWT_SIGNING_KEY=getattr(settings, other)):
        assert [message.id for message in jwt_signing_key_is_its_own()] == ["cherrylove.E005"]
    with override_settings(JWT_SIGNING_KEY=""):
        assert [message.id for message in jwt_signing_key_is_its_own()] == ["cherrylove.E004"]
    assert jwt_signing_key_is_its_own() == []

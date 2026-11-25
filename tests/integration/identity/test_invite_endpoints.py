"""Invite endpoints over HTTP (IMPL-API-001 F2.8; REQ-F-AUTH-02…06, REQ-F-AUTH-10, DEC-018, ADR-004 §2)."""

from __future__ import annotations

import io
import uuid
from datetime import date, timedelta

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client

from cherrylove.identity.application.commands.invites import IssueInviteToken
from cherrylove.identity.infrastructure.adapters.jwt_tokens import MinimalAccessToken
from cherrylove.identity.infrastructure.adapters.tokens import SecretsTokenGenerator
from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, Invite, User
from cherrylove.identity.infrastructure.repositories import DjangoInviteRepository
from cherrylove.shared.infrastructure.clock import SystemClock

pytestmark = pytest.mark.integration
ONBOARDING = {"name": "Camila", "birth_date": "1996-03-09", "password": "correct horse battery"}


@pytest.fixture(autouse=True)
def _fresh_throttles() -> None:
    cache.clear()


def _couple_with_tokens() -> tuple[uuid.UUID, str, str]:
    emails = [f"p{slot}.{uuid.uuid4().hex[:8]}@example.com" for slot in (1, 2)]
    out = io.StringIO()
    call_command("create_couple", *emails, stdout=out)
    couple_id = uuid.UUID(out.getvalue().strip())
    issue = IssueInviteToken(DjangoInviteRepository(), SecretsTokenGenerator(), SystemClock())
    tokens = [issue.execute(Invite.objects.get(couple_id=couple_id, slot=slot).id) for slot in (1, 2)]
    return couple_id, tokens[0], tokens[1]


def _code(response: object) -> str:
    return str(response.json()["code"])  # type: ignore[attr-defined]


@pytest.mark.req("REQ-F-AUTH-03")
@pytest.mark.django_db(transaction=True)
def test_onboarding_on_web_then_mobile(client: Client) -> None:
    couple_id, first, second = _couple_with_tokens()

    preview = client.get(f"/api/v1/invites/{first}")
    assert preview.status_code == 200
    assert preview.json()["relationship_start_known"] is False

    web = client.post(
        f"/api/v1/invites/{first}/accept",
        {**ONBOARDING, "relationship_start": "2023-02-14", "language": "en"},
        content_type="application/json",
        headers={"X-CherryLove-Client": "web"},
    )
    assert web.status_code == 201
    assert "refresh" not in web.json()
    cookie = web.cookies["cl_refresh"]
    assert cookie["httponly"]
    assert cookie["secure"]
    assert cookie["samesite"] == "Strict"
    assert cookie["path"] == "/api/v1/auth/"
    first_user = User.objects.get(membership__couple_id=couple_id, membership__slot=1)
    assert MinimalAccessToken(web.json()["access"])["sub"] == str(first_user.id), "partner 1 uses the app alone"
    assert first_user.language == "en"
    assert Couple.objects.get(id=couple_id).relationship_start == date(2023, 2, 14)

    assert client.get(f"/api/v1/invites/{second}").json()["relationship_start_known"] is True
    mobile = client.post(
        f"/api/v1/invites/{second}/accept",
        {**ONBOARDING, "name": "Andrés", "relationship_start": "2000-01-01"},
        content_type="application/json",
        headers={"X-CherryLove-Client": "mobile"},
    )
    assert mobile.status_code == 201
    assert mobile.json()["refresh"]
    assert "cl_refresh" not in mobile.cookies
    assert Couple.objects.get(id=couple_id).relationship_start == date(2023, 2, 14)
    assert CoupleMembership.objects.filter(couple_id=couple_id).count() == 2

    reused = client.post(f"/api/v1/invites/{first}/accept", ONBOARDING, content_type="application/json")
    assert (reused.status_code, _code(reused)) == (404, "not_found")


@pytest.mark.req("REQ-F-AUTH-02")
@pytest.mark.django_db(transaction=True)
def test_revoked_expired_archived_and_unknown_invites(client: Client) -> None:
    couple_id, first, second = _couple_with_tokens()
    Invite.objects.filter(couple_id=couple_id, slot=1).update(status="revoked")
    assert _code(client.get(f"/api/v1/invites/{first}")) == "invite_revoked"
    invite = Invite.objects.get(couple_id=couple_id, slot=2)
    Invite.objects.filter(id=invite.id).update(expires_at=invite.created_at - timedelta(seconds=1))
    assert _code(client.get(f"/api/v1/invites/{second}")) == "invite_expired"
    Invite.objects.filter(id=invite.id).update(expires_at=invite.created_at + timedelta(hours=72))
    Couple.objects.filter(id=couple_id).update(status="archived", archived_at=invite.created_at)
    response = client.post(f"/api/v1/invites/{second}/accept", ONBOARDING, content_type="application/json")
    assert (response.status_code, _code(response)) == (409, "couple_archived")
    assert client.get("/api/v1/invites/not-a-token").status_code == 404


@pytest.mark.req("REQ-F-AUTH-03")
@pytest.mark.django_db(transaction=True)
def test_invalid_onboarding_is_a_field_error(client: Client) -> None:
    _, first, _ = _couple_with_tokens()
    response = client.post(
        f"/api/v1/invites/{first}/accept", {**ONBOARDING, "password": "short"}, content_type="application/json"
    )
    assert response.status_code == 400
    assert response.json()["errors"] == [{"pointer": "/password", "code": "too_short"}]


@pytest.mark.req("REQ-N-SEC-04")
@pytest.mark.django_db(transaction=True)
def test_invite_endpoints_are_throttled_at_10_per_hour_per_ip(client: Client) -> None:
    statuses = [client.get("/api/v1/invites/unknown").status_code for _ in range(11)]
    assert statuses[:10] == [404] * 10
    assert statuses[10] == 429
    throttled = client.get("/api/v1/invites/unknown")
    assert _code(throttled) == "rate_limited"
    assert int(throttled["Retry-After"]) > 0

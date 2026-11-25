"""Identity rows of the permission matrix (IMPL-API-001 F2.17; roles-actuators, ADR-005 §7, REQ-N-SEC-01).

Rows owned by identity in F2: "Complete onboarding" and "Read shared content" for the couple header. Staff
rows (create couple / invite / archive, metadata) are admin-only and arrive with the admin in F9.
"""

from __future__ import annotations

import io
import uuid

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client

from cherrylove.identity.application.commands.invites import IssueInviteToken
from cherrylove.identity.infrastructure.adapters.jwt_tokens import JwtTokenIssuer
from cherrylove.identity.infrastructure.adapters.tokens import SecretsTokenGenerator
from cherrylove.identity.infrastructure.orm import Invite, User
from cherrylove.identity.infrastructure.repositories import DjangoInviteRepository
from cherrylove.shared.domain.ids import UserId
from cherrylove.shared.infrastructure.clock import SystemClock

pytestmark = pytest.mark.integration
ONBOARDING = {"name": "Camila", "birth_date": "1996-03-09", "password": "correct horse battery"}


@pytest.fixture(autouse=True)
def _fresh_throttles() -> None:
    cache.clear()


def _invite_tokens() -> tuple[str, str]:
    emails = [f"m{slot}.{uuid.uuid4().hex[:8]}@example.com" for slot in (1, 2)]
    out = io.StringIO()
    call_command("create_couple", *emails, stdout=out)
    couple_id = uuid.UUID(out.getvalue().strip())
    issue = IssueInviteToken(DjangoInviteRepository(), SecretsTokenGenerator(), SystemClock())
    first, second = (issue.execute(Invite.objects.get(couple_id=couple_id, slot=slot).id) for slot in (1, 2))
    return first, second


def _accept(client: Client, token: str) -> dict[str, str]:
    response = client.post(f"/api/v1/invites/{token}/accept", ONBOARDING, content_type="application/json")
    assert response.status_code == 201
    pair: dict[str, str] = response.json()
    return pair


def _header(client: Client, access: str | None) -> int:
    headers = {"Authorization": f"Bearer {access}"} if access else {}
    return client.get("/api/v1/couple", headers=headers).status_code


@pytest.mark.req("REQ-F-AUTH-03")
@pytest.mark.django_db(transaction=True)
def test_row_complete_onboarding_invitee_allowed(client: Client) -> None:
    first, _ = _invite_tokens()
    assert _accept(client, first)["access"]
    again = client.post(f"/api/v1/invites/{first}/accept", ONBOARDING, content_type="application/json")
    assert again.status_code == 404, "an accepted invite is gone"


@pytest.mark.req("REQ-N-SEC-01")
@pytest.mark.django_db(transaction=True)
def test_row_read_shared_content_both_partners_allowed_invitee_and_staff_denied(client: Client) -> None:
    first, second = _invite_tokens()
    assert _header(client, None) == 401, "invitee: no session before onboarding"
    own, partners = _accept(client, first), _accept(client, second)
    assert (_header(client, own["access"]), _header(client, partners["access"])) == (200, 200)
    staff = User.objects.create_user(f"s.{uuid.uuid4().hex[:8]}@example.com", "staff passphrase 1", name="S")
    User.objects.filter(id=staff.id).update(is_staff=True)
    assert _header(client, JwtTokenIssuer().issue(UserId(staff.id)).access) == 401, "staff never act as partners"

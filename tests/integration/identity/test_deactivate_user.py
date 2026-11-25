"""Deactivate user against the real stack (IMPL-API-001 F2.15; REQ-F-AUTH-09, REQ-F-ADM-01, ADR-005)."""

from __future__ import annotations

import json
import uuid

import pytest
from django.db import connections
from django.test import Client

from cherrylove.identity import wiring
from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, User
from cherrylove.shared.domain.ids import UserId

pytestmark = pytest.mark.integration
PASSWORD = "correct horse battery"


@pytest.mark.req("REQ-F-AUTH-09")
@pytest.mark.django_db(transaction=True)
def test_a_still_valid_access_token_is_refused_right_after_deactivation(client: Client) -> None:
    user = User.objects.create_user(f"d.{uuid.uuid4().hex[:8]}@example.com", PASSWORD, name="D")
    CoupleMembership.objects.create(couple=Couple.objects.create(), user=user, slot=1)
    pair = client.post(
        "/api/v1/auth/login",
        {"email": user.email, "password": PASSWORD, "client": "mobile"},
        content_type="application/json",
    ).json()
    wiring.actor_resolver().resolve(UserId(user.id))  # the Actor is cached, as after any partner request

    wiring.deactivate_user().execute(UserId(user.id))

    bearer = {"Authorization": f"Bearer {pair['access']}"}
    logout = client.post("/api/v1/auth/logout", content_type="application/json", headers=bearer)
    assert (logout.status_code, logout.json()["code"]) == (401, "not_authenticated"), "not after 10 minutes"
    refresh = client.post("/api/v1/auth/refresh", {"refresh": pair["refresh"]}, content_type="application/json")
    assert refresh.status_code == 401
    with connections["default"].cursor() as cursor:
        cursor.execute(
            "SELECT changes FROM audit_event WHERE action = 'admin.user_deactivated' AND entity_id = %s", [user.id]
        )
        [(changes,)] = cursor.fetchall()
    assert json.loads(changes)["revoked_sessions"] == {"from": None, "to": 1}

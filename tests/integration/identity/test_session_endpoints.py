"""Login, refresh and logout over HTTP (IMPL-API-001 F2.10; REQ-F-AUTH-07, REQ-F-ACC-06, REQ-N-SEC-03, ADR-004 §2-3)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from django.db import connections
from django.test import Client

from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, User
from cherrylove.shared.application.audit_log import email_fingerprint

pytestmark = pytest.mark.integration
PASSWORD = "correct horse battery"
WEB = {"X-CherryLove-Client": "web"}


def _partner() -> User:
    user = User.objects.create_user(f"p.{uuid.uuid4().hex[:8]}@example.com", PASSWORD, name="P")
    CoupleMembership.objects.create(couple=Couple.objects.create(), user=user, slot=1)
    return user


def _login(client: Client, email: str, password: str, kind: str) -> Any:
    return client.post(
        "/api/v1/auth/login", {"email": email, "password": password, "client": kind}, content_type="application/json"
    )


def _audit(action: str) -> list[dict[str, Any]]:
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT changes, entity_id FROM audit_event WHERE action = %s", [action])
        return [{"changes": json.loads(row[0]), "entity_id": row[1]} for row in cursor.fetchall()]


@pytest.mark.req("REQ-N-SEC-03")
@pytest.mark.django_db(transaction=True)
def test_web_login_puts_the_refresh_only_in_the_cookie(client: Client) -> None:
    user = _partner()
    response = _login(client, user.email, PASSWORD, "web")
    assert response.status_code == 200
    assert set(response.json()) == {"access", "access_expires_at"}
    cookie = response.cookies["cl_refresh"]
    assert (cookie["httponly"], cookie["secure"], cookie["samesite"], cookie["path"]) == (
        True,
        True,
        "Strict",
        "/api/v1/auth/",
    )
    assert any(e["entity_id"] == user.id for e in _audit("auth.login"))


@pytest.mark.req("REQ-F-AUTH-07")
@pytest.mark.django_db(transaction=True)
def test_mobile_login_returns_the_pair_and_refresh_rotates(client: Client) -> None:
    user = _partner()
    first = _login(client, user.email, PASSWORD, "mobile").json()
    assert first["refresh"]
    rotated = client.post("/api/v1/auth/refresh", {"refresh": first["refresh"]}, content_type="application/json")
    assert rotated.status_code == 200
    assert rotated.json()["refresh"] != first["refresh"]
    replay = client.post("/api/v1/auth/refresh", {"refresh": first["refresh"]}, content_type="application/json")
    assert (replay.status_code, replay.json()["code"]) == (401, "not_authenticated")


@pytest.mark.req("REQ-F-AUTH-07")
@pytest.mark.django_db(transaction=True)
def test_wrong_password_and_unknown_email_answer_the_same_and_are_audited(client: Client) -> None:
    user = _partner()
    wrong = _login(client, user.email, "not the password", "mobile")
    unknown = _login(client, "nobody@example.com", PASSWORD, "mobile")
    assert (wrong.status_code, wrong.json()["code"]) == (unknown.status_code, unknown.json()["code"])
    assert wrong.json()["code"] == "invalid_credentials"
    hmacs = [e["changes"]["email_hmac"]["to"] for e in _audit("auth.login_failed") if "email_hmac" in e["changes"]]
    assert email_fingerprint(user.email, "local-only-audit-hmac-not-a-secret-0001") in hmacs
    assert user.email not in json.dumps(_audit("auth.login_failed"))


@pytest.mark.req("REQ-N-SEC-03")
@pytest.mark.django_db(transaction=True)
def test_cookie_calls_need_the_web_client_header(client: Client) -> None:
    user = _partner()
    _login(client, user.email, PASSWORD, "web")
    without = client.post("/api/v1/auth/refresh", content_type="application/json")
    assert (without.status_code, without.json()["code"]) == (403, "client_header_required")
    rotated = client.post("/api/v1/auth/refresh", content_type="application/json", headers=WEB)
    assert rotated.status_code == 200
    assert "refresh" not in rotated.json()
    assert rotated.cookies["cl_refresh"].value


@pytest.mark.req("REQ-F-ACC-06")
@pytest.mark.django_db(transaction=True)
def test_logout_blacklists_the_refresh_and_clears_the_web_cookie(client: Client) -> None:
    user = _partner()
    access = _login(client, user.email, PASSWORD, "web").json()["access"]
    unauthenticated = client.post("/api/v1/auth/logout", content_type="application/json", headers=WEB)
    assert unauthenticated.status_code == 401
    logout = client.post(
        "/api/v1/auth/logout", content_type="application/json", headers={**WEB, "Authorization": f"Bearer {access}"}
    )
    assert logout.status_code == 204
    assert logout.cookies["cl_refresh"].value == ""
    after = client.post("/api/v1/auth/refresh", content_type="application/json", headers=WEB)
    assert after.status_code == 401
    assert any(e["entity_id"] == user.id for e in _audit("auth.logout"))

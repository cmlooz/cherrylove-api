"""Auth throttles that fail closed (IMPL-API-001 F2.12; REQ-N-SEC-04, ADR-004 §4, ADR-011 §2)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client, override_settings

pytestmark = pytest.mark.integration
REDIS_DOWN = override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "redis://127.0.0.1:1/0",
            "OPTIONS": {"socket_connect_timeout": 0.2, "socket_timeout": 0.2},
        }
    }
)


@pytest.fixture(autouse=True)
def _fresh_counters() -> None:
    cache.clear()


def _login(client: Client, email: str, ip: str = "198.51.100.1") -> Any:
    return client.post(
        "/api/v1/auth/login",
        {"email": email, "password": "wrong password", "client": "mobile"},
        content_type="application/json",
        REMOTE_ADDR=ip,
    )


@pytest.mark.req("REQ-N-SEC-04")
@pytest.mark.django_db(transaction=True)
def test_login_allows_5_per_minute_per_ip_and_email(client: Client) -> None:
    email = f"target.{uuid.uuid4().hex[:8]}@example.com"
    statuses = [_login(client, email).status_code for _ in range(6)]
    assert statuses == [401] * 5 + [429]
    assert _login(client, email).json()["code"] == "rate_limited"
    assert _login(client, f"other.{email}").status_code == 401, "another email from the same IP is its own bucket"
    assert _login(client, email, ip="198.51.100.2").status_code == 401, "same email from another IP too"


@pytest.mark.req("REQ-N-SEC-04")
@pytest.mark.django_db(transaction=True)
@REDIS_DOWN
def test_redis_down_fails_closed_on_auth_scopes_only(client: Client) -> None:
    login = _login(client, "camila@example.com")
    assert (login.status_code, login.json()["code"]) == (503, "service_unavailable")
    accept = client.post("/api/v1/invites/unknown/accept", {}, content_type="application/json")
    assert (accept.status_code, accept.json()["code"]) == (503, "service_unavailable")
    preview = client.get("/api/v1/invites/unknown")
    assert (preview.status_code, preview.json()["code"]) == (404, "not_found"), "viewing an invite fails open"

"""Password recovery over HTTP (IMPL-API-001 F2.13; REQ-F-AUTH-08, ADR-004 §4, ADR-012 §4, ADR-011 §2)."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
import uuid
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django_tasks_db.models import DBTaskResult

from cherrylove.identity.application.commands.password_recovery import SEND_PASSWORD_RECOVERY
from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, User
from cherrylove.shared.infrastructure.django_job_queue import run_job

pytestmark = pytest.mark.integration
MAILPIT_API = os.environ.get("MAILPIT_API", "http://127.0.0.1:8025")
SMTP = override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend")
PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def _fresh_counters() -> None:
    cache.clear()


def _partner(language: str = "es") -> User:
    user = User.objects.create_user(f"r.{uuid.uuid4().hex[:8]}@example.com", PASSWORD, name="Camila", language=language)
    CoupleMembership.objects.create(couple=Couple.objects.create(), user=user, slot=1)
    return user


def _request(client: Client, email: str) -> Any:
    return client.post("/api/v1/auth/password-recovery", {"email": email}, content_type="application/json")


def _recovery_jobs_for(user: User) -> list[DBTaskResult[Any, Any]]:
    return [
        row
        for row in DBTaskResult.objects.all()
        if row.args_kwargs["args"][0] == SEND_PASSWORD_RECOVERY
        and row.args_kwargs["args"][1]["user_id"] == str(user.id)
    ]


def _send(user: User) -> tuple[str, str, str]:
    """Run the queued job, then read the mail from Mailpit: (subject, uid, token)."""
    [job] = _recovery_jobs_for(user)
    run_job.call(*job.args_kwargs["args"])
    query = urllib.parse.quote(f"to:{user.email}")
    with urllib.request.urlopen(f"{MAILPIT_API}/api/v1/search?query={query}", timeout=5) as response:
        [message] = json.load(response)["messages"]
    with urllib.request.urlopen(f"{MAILPIT_API}/api/v1/message/{message['ID']}", timeout=5) as response:
        text = json.load(response)["Text"]
    match = re.search(r"/password-recovery/([^/\s]+)/([^/\s]+)", text)
    assert match is not None
    return str(message["Subject"]), match.group(1), match.group(2)


def _confirm(client: Client, uid: str, token: str, password: str = "a brand new passphrase") -> Any:
    return client.post(
        "/api/v1/auth/password-recovery/confirm",
        {"uid": uid, "token": token, "new_password": password},
        content_type="application/json",
    )


@pytest.mark.req("REQ-F-AUTH-08")
@pytest.mark.django_db(transaction=True)
def test_the_answer_is_identical_whether_the_email_exists_or_not(client: Client) -> None:
    user = _partner()
    known, unknown = _request(client, user.email), _request(client, "nobody@example.com")
    assert (known.status_code, known.content) == (unknown.status_code, unknown.content) == (202, b"")
    assert len(_recovery_jobs_for(user)) == 1


@pytest.mark.req("REQ-F-AUTH-08")
@pytest.mark.django_db(transaction=True)
@SMTP
@pytest.mark.parametrize(("language", "subject"), [("es", "Recupera"), ("en", "Reset")])
def test_the_email_is_in_the_account_language_and_the_token_works_once(
    client: Client, language: str, subject: str
) -> None:
    user = _partner(language)
    _request(client, user.email)
    sent_subject, uid, token = _send(user)
    assert sent_subject.startswith(subject)

    assert _confirm(client, uid, token).status_code == 204
    user.refresh_from_db()
    assert user.check_password("a brand new passphrase")
    reused = _confirm(client, uid, token, "yet another passphrase")
    assert reused.status_code == 400
    assert reused.json()["errors"] == [{"pointer": "/token", "code": "invalid_token"}], "dead after the change"


@pytest.mark.req("REQ-F-AUTH-08")
@pytest.mark.django_db(transaction=True)
def test_confirming_revokes_every_session(client: Client) -> None:
    from cherrylove.identity.infrastructure.adapters.recovery import DjangoRecoveryAccounts  # noqa: PLC0415

    user = _partner()
    refresh = client.post(
        "/api/v1/auth/login",
        {"email": user.email, "password": PASSWORD, "client": "mobile"},
        content_type="application/json",
    ).json()["refresh"]
    accounts = DjangoRecoveryAccounts()
    recipient = accounts.recipient(user.id)
    assert recipient is not None
    assert _confirm(client, recipient.uid, accounts.issue_token(user.id)).status_code == 204
    refreshed = client.post("/api/v1/auth/refresh", {"refresh": refresh}, content_type="application/json")
    assert refreshed.status_code == 401


@pytest.mark.req("REQ-F-AUTH-08")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(("uid", "token"), [("", ""), ("not-base64", "x"), ("MDE5YTVi", "wrong-token")])
def test_a_bad_link_is_one_field_error(client: Client, uid: str, token: str) -> None:
    response = _confirm(client, uid, token)
    assert response.status_code == 400
    assert response.json()["errors"] == [{"pointer": "/token", "code": "invalid_token"}]


@pytest.mark.req("REQ-N-SEC-04")
@pytest.mark.django_db(transaction=True)
def test_recovery_is_throttled_at_3_per_hour_per_email(client: Client) -> None:
    email = f"t.{uuid.uuid4().hex[:8]}@example.com"
    assert [_request(client, email).status_code for _ in range(4)] == [202, 202, 202, 429]
    assert _request(client, f"other.{email}").status_code == 202


@pytest.mark.req("REQ-N-SEC-04")
@pytest.mark.django_db(transaction=True)
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "redis://127.0.0.1:1/0",
            "OPTIONS": {"socket_connect_timeout": 0.2, "socket_timeout": 0.2},
        }
    }
)
def test_recovery_fails_closed_when_redis_is_down(client: Client) -> None:
    response = _request(client, "camila@example.com")
    assert (response.status_code, response.json()["code"]) == (503, "service_unavailable")

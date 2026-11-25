"""F2 phase journey (IMPL-API-001 F2 phase integration test; REQ-F-AUTH-01…07, REQ-F-HOME-01, ADR-004 §3).

create_couple → invites in Mailpit → partner 1 accepts (sets the relationship start) and logs in on web →
partner 2 accepts (not asked) and logs in on mobile → /couple shows both → refresh rotates → the reused
refresh kills every session of partner 2 → an audit row for every step.
"""

from __future__ import annotations

import io
import json
import os
import re
import urllib.parse
import urllib.request
import uuid
from typing import Any

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.db import connections
from django.test import Client, override_settings
from django_tasks_db.models import DBTaskResult

from cherrylove.identity.application.commands.create_couple import SEND_INVITE_EMAIL
from cherrylove.identity.infrastructure.orm import Invite, User
from cherrylove.shared.infrastructure.django_job_queue import run_job

pytestmark = pytest.mark.integration
MAILPIT_API = os.environ.get("MAILPIT_API", "http://127.0.0.1:8025")
PASSWORD = "correct horse battery"
WEB = {"X-CherryLove-Client": "web"}


def _invite_token(email: str) -> str:
    query = urllib.parse.quote(f"to:{email}")
    with urllib.request.urlopen(f"{MAILPIT_API}/api/v1/search?query={query}", timeout=5) as response:
        [message] = json.load(response)["messages"]
    with urllib.request.urlopen(f"{MAILPIT_API}/api/v1/message/{message['ID']}", timeout=5) as response:
        text = json.load(response)["Text"]
    match = re.search(r"/invites/([A-Za-z0-9_-]+)", text)
    assert match is not None
    return match.group(1)


def _actions_for(entity_ids: set[str]) -> list[str]:
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT action, entity_id FROM audit_event ORDER BY occurred_at, id")
        return [row[0] for row in cursor.fetchall() if str(row[1]) in entity_ids]


def _login(client: Client, email: str, kind: str, headers: dict[str, str] | None = None) -> Any:
    return client.post(
        "/api/v1/auth/login",
        {"email": email, "password": PASSWORD, "client": kind},
        content_type="application/json",
        headers=headers or {},
    )


@pytest.mark.req("REQ-F-AUTH-01")
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend")
def test_two_partners_onboard_sign_in_and_a_stolen_refresh_is_caught() -> None:
    cache.clear()
    camila, andres = (f"{name}.{uuid.uuid4().hex[:8]}@example.com" for name in ("camila", "andres"))
    out = io.StringIO()
    call_command("create_couple", camila, andres, stdout=out)
    couple_id = out.getvalue().strip()
    for job in DBTaskResult.objects.all():
        args = job.args_kwargs["args"]
        if args[0] == SEND_INVITE_EMAIL:
            run_job.call(*args)

    web, mobile = Client(), Client()
    first = web.post(
        f"/api/v1/invites/{_invite_token(camila)}/accept",
        {"name": "Camila", "birth_date": "1996-03-09", "password": PASSWORD, "relationship_start": "2023-02-14"},
        content_type="application/json",
        headers=WEB,
    )
    assert first.status_code == 201
    assert _login(web, camila, "web", WEB).status_code == 200

    second_token = _invite_token(andres)
    assert mobile.get(f"/api/v1/invites/{second_token}").json()["relationship_start_known"] is True
    second = mobile.post(
        f"/api/v1/invites/{second_token}/accept",
        {"name": "Andrés", "birth_date": "1995-07-01", "password": PASSWORD},
        content_type="application/json",
    )
    assert second.status_code == 201
    pair = _login(mobile, andres, "mobile").json()

    header = mobile.get("/api/v1/couple", headers={"Authorization": f"Bearer {pair['access']}"}).json()
    assert [partner["name"] for partner in header["partners"]] == ["Camila", "Andrés"]
    assert header["relationship_start"] == "2023-02-14"

    rotated = mobile.post("/api/v1/auth/refresh", {"refresh": pair["refresh"]}, content_type="application/json")
    assert rotated.status_code == 200
    reused = mobile.post("/api/v1/auth/refresh", {"refresh": pair["refresh"]}, content_type="application/json")
    assert reused.status_code == 401
    after = mobile.post("/api/v1/auth/refresh", {"refresh": rotated.json()["refresh"]}, content_type="application/json")
    assert after.status_code == 401, "every session of partner 2 is revoked"
    assert web.post("/api/v1/auth/refresh", content_type="application/json", headers=WEB).status_code == 200

    users = {str(user_id) for user_id in User.objects.filter(email__in=[camila, andres]).values_list("id", flat=True)}
    invites = {str(invite_id) for invite_id in Invite.objects.filter(couple_id=couple_id).values_list("id", flat=True)}
    assert _actions_for({couple_id}) == ["admin.couple_created"]
    assert _actions_for(invites).count("invite.accepted") == 2
    actions = _actions_for(users)
    # Refreshed: the mobile rotation and the web cookie. Reused: only the replay of the rotated token.
    assert (actions.count("auth.login"), actions.count("auth.refreshed"), actions.count("auth.refresh_reused")) == (
        2,
        2,
        1,
    )

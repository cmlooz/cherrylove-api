"""The invite email job against Mailpit (IMPL-API-001 F2.7; REQ-F-AUTH-01, ADR-012 §4, ADR-013 §2)."""

from __future__ import annotations

import io
import json
import os
import urllib.parse
import urllib.request
import uuid
from typing import Any

import pytest
from django.core.management import call_command
from django.test import override_settings

from cherrylove.identity.application.commands.create_couple import SEND_INVITE_EMAIL
from cherrylove.identity.infrastructure.orm import Invite
from cherrylove.shared.infrastructure.django_job_queue import run_job

pytestmark = pytest.mark.integration
MAILPIT_API = os.environ.get("MAILPIT_API", "http://127.0.0.1:8025")
SMTP = override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend")


def _messages_to(email: str) -> list[dict[str, Any]]:
    query = urllib.parse.quote(f"to:{email}")
    with urllib.request.urlopen(f"{MAILPIT_API}/api/v1/search?query={query}", timeout=5) as response:
        found: list[dict[str, Any]] = json.load(response)["messages"]
    return found


def _text(message_id: str) -> str:
    with urllib.request.urlopen(f"{MAILPIT_API}/api/v1/message/{message_id}", timeout=5) as response:
        text: str = json.load(response)["Text"]
    return text


@pytest.mark.req("REQ-F-AUTH-01")
@pytest.mark.django_db(transaction=True)
@SMTP
def test_mailpit_receives_one_bilingual_email_and_a_rerun_sends_nothing() -> None:
    camila = f"camila.{uuid.uuid4().hex[:8]}@example.com"
    call_command("create_couple", camila, f"andres.{uuid.uuid4().hex[:8]}@example.com", stdout=io.StringIO())
    invite = Invite.objects.get(email=camila)
    key = f"email:invite:{invite.id}"

    assert run_job.call(SEND_INVITE_EMAIL, {"invite_id": str(invite.id)}, key) is True
    assert run_job.call(SEND_INVITE_EMAIL, {"invite_id": str(invite.id)}, key) is False

    [message] = _messages_to(camila)
    text = _text(message["ID"])
    assert text.index("Te invitaron") < text.index("You have been invited")
    assert "/invites/" in text
    invite.refresh_from_db()
    assert invite.token_hash is not None
    assert invite.sent_at is not None

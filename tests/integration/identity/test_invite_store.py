"""Invites on PostgreSQL (IMPL-API-001 F2.6; REQ-F-AUTH-02, DEC-017, DATA-001 §3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from django.db import IntegrityError, connections, transaction

from cherrylove.identity.application.commands.invites import IssueInviteToken
from cherrylove.identity.domain.invite_token import hash_token
from cherrylove.identity.infrastructure.adapters.tokens import SecretsTokenGenerator
from cherrylove.identity.infrastructure.orm import Couple
from cherrylove.identity.infrastructure.repositories import DjangoInviteRepository
from cherrylove.shared.domain.ids import CoupleId
from cherrylove.shared.infrastructure.clock import SystemClock

pytestmark = pytest.mark.integration
LATER = datetime(2026, 12, 1, tzinfo=UTC)


@pytest.mark.req("REQ-F-AUTH-02")
@pytest.mark.django_db
def test_one_pending_invite_per_seat() -> None:
    repo, couple = DjangoInviteRepository(), CoupleId(Couple.objects.create().id)
    first = uuid.uuid7()
    repo.add_pending(first, couple, 1, "a@example.com", LATER)
    repo.add_pending(uuid.uuid7(), couple, 2, "b@example.com", LATER)
    with pytest.raises(IntegrityError), transaction.atomic():
        repo.add_pending(uuid.uuid7(), couple, 1, "a@example.com", LATER)
    repo.revoke(first)
    repo.add_pending(uuid.uuid7(), couple, 1, "a@example.com", LATER + timedelta(hours=1))
    assert repo.pending_for_seat(couple, 1) is not None


@pytest.mark.req("REQ-F-AUTH-02")
@pytest.mark.django_db
def test_the_database_never_holds_the_raw_token() -> None:
    repo, couple, invite_id = DjangoInviteRepository(), CoupleId(Couple.objects.create().id), uuid.uuid7()
    repo.add_pending(invite_id, couple, 1, "a@example.com", LATER)
    raw = IssueInviteToken(repo, SecretsTokenGenerator(), SystemClock()).execute(invite_id)
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT token_hash, sent_at FROM identity_invite WHERE id = %s", [invite_id])
        row = cursor.fetchone()
    assert row is not None
    assert bytes(row[0]) == hash_token(raw)
    assert raw.encode() not in bytes(row[0])
    assert row[1] is not None

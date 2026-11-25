"""`manage.py create_couple` end to end on PostgreSQL (IMPL-API-001 F2.5; REQ-F-AUTH-01/10, REQ-F-ADM-01)."""

from __future__ import annotations

import io
import uuid

import pytest
from django.core.management import CommandError, call_command
from django.db import connections
from django_tasks_db.models import DBTaskResult

from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, Invite, User
from cherrylove.shared.infrastructure.orm import CoupleDataKey
from cherrylove.sync.infrastructure.orm import SyncState

pytestmark = pytest.mark.integration


def _create(*emails: str) -> uuid.UUID:
    out = io.StringIO()
    call_command("create_couple", *emails, stdout=out)
    return uuid.UUID(out.getvalue().strip())


def _audited(action: str, entity_id: uuid.UUID) -> int:
    with connections["default"].cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM audit_event WHERE action = %s AND entity_id = %s AND actor_type = 'system'",
            [action, entity_id],
        )
        row = cursor.fetchone()
    assert row is not None
    return int(row[0])


def _invite_jobs(invite_ids: set[uuid.UUID]) -> int:
    keys = {f"email:invite:{invite_id}" for invite_id in invite_ids}
    return sum(1 for row in DBTaskResult.objects.all() if row.args_kwargs["args"][2] in keys)


@pytest.mark.req("REQ-F-AUTH-01")
@pytest.mark.django_db(transaction=True)
def test_one_transaction_creates_everything_the_couple_needs() -> None:
    couple_id = _create("Camila@Example.com", "andres@example.com")

    couple = Couple.objects.get(id=couple_id)
    assert (couple.status, couple.timezone) == ("active", "America/Bogota")
    assert SyncState.objects.get(couple_id=couple_id).last_seq == 0
    assert CoupleDataKey.objects.filter(couple_id=couple_id, key_id=1).count() == 1
    invites = list(Invite.objects.filter(couple_id=couple_id).order_by("slot"))
    assert [(i.slot, i.email, i.status, i.token_hash) for i in invites] == [
        (1, "camila@example.com", "pending", None),
        (2, "andres@example.com", "pending", None),
    ]
    assert _invite_jobs({i.id for i in invites}) == 2
    assert _audited("admin.couple_created", couple_id) == 1


@pytest.mark.req("REQ-F-AUTH-10")
@pytest.mark.django_db(transaction=True)
def test_an_email_already_in_a_couple_creates_nothing() -> None:
    user = User.objects.create_user("camila@example.com", "correct horse battery", name="Camila")
    CoupleMembership.objects.create(couple=Couple.objects.create(), user=user, slot=1)
    couples_before = Couple.objects.count()

    with pytest.raises(CommandError, match="email_already_in_couple"):
        _create("camila@example.com", "andres@example.com")

    assert Couple.objects.count() == couples_before
    assert not Invite.objects.filter(email="andres@example.com").exists()

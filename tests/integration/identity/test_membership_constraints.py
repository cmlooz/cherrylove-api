"""Couple and membership invariants live in the database (IMPL-API-001 F2.2; REQ-F-AUTH-05, DATA-001 §3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.db import DatabaseError, IntegrityError, ProgrammingError, connections, transaction

from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, User

pytestmark = pytest.mark.integration
DBS = ["default", "maintenance"]


def _user(email: str, **extra: object) -> User:
    return User.objects.create_user(email, "correct horse battery", name=email.split("@", maxsplit=1)[0], **extra)


def _couple_with(*users: User) -> Couple:
    couple = Couple.objects.create()
    for slot, user in enumerate(users, start=1):
        CoupleMembership.objects.create(couple=couple, user=user, slot=slot)
    return couple


@pytest.mark.req("REQ-F-AUTH-05")
@pytest.mark.django_db
def test_two_partners_fit() -> None:
    couple = _couple_with(_user("a@example.com"), _user("b@example.com"))
    assert couple.memberships.count() == 2


@pytest.mark.req("REQ-F-AUTH-05")
@pytest.mark.django_db
@pytest.mark.parametrize("slot", [1, 3])
def test_a_third_member_is_refused(slot: int) -> None:
    couple = _couple_with(_user("a@example.com"), _user("b@example.com"))
    with pytest.raises(IntegrityError), transaction.atomic():
        CoupleMembership.objects.create(couple=couple, user=_user("c@example.com"), slot=slot)


@pytest.mark.req("REQ-F-AUTH-05")
@pytest.mark.django_db
def test_a_user_belongs_to_one_couple_only() -> None:
    shared = _user("a@example.com")
    _couple_with(shared)
    with pytest.raises(IntegrityError), transaction.atomic():
        CoupleMembership.objects.create(couple=Couple.objects.create(), user=shared, slot=1)


@pytest.mark.req("REQ-F-AUTH-05")
@pytest.mark.django_db
@pytest.mark.parametrize("column", ["couple_id", "user_id"])
def test_a_membership_never_switches_couple_or_user(column: str) -> None:
    couple = _couple_with(_user("a@example.com"))
    other = Couple.objects.create() if column == "couple_id" else None
    target = other.id if other else _user("b@example.com").id
    with (
        pytest.raises(DatabaseError, match="never changes"),
        transaction.atomic(),
        connections["default"].cursor() as cursor,
    ):
        cursor.execute(f"UPDATE identity_couple_membership SET {column} = %s WHERE couple_id = %s", [target, couple.id])


@pytest.mark.req("REQ-F-AUTH-05")
@pytest.mark.django_db
@pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
def test_staff_users_are_never_partners(flag: str) -> None:
    staff = _user("staff@example.com", **{flag: True})
    with pytest.raises(DatabaseError, match="never partners"), transaction.atomic():
        _couple_with(staff)


@pytest.mark.req("REQ-F-AUTH-05")
@pytest.mark.django_db(databases=DBS)
def test_only_the_maintenance_role_deletes_memberships() -> None:
    couple = _couple_with(_user("a@example.com"))
    with (
        pytest.raises(ProgrammingError, match="permission denied"),
        transaction.atomic(),
        connections["default"].cursor() as cursor,
    ):
        cursor.execute("DELETE FROM identity_couple_membership WHERE couple_id = %s", [couple.id])


@pytest.mark.req("REQ-F-AUTH-09")
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "archived_at"),
    [("archived", None), ("active", datetime(2026, 11, 1, tzinfo=UTC)), ("ended", None)],
)
def test_couple_status_and_archived_at_agree(status: str, archived_at: datetime | None) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Couple.objects.create(status=status, archived_at=archived_at)

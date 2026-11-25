"""Account use cases with fakes (IMPL-API-001 F2.16; REQ-F-ACC-02/03/04, REQ-F-HOME-01, DEC-025, DEC-051)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import pytest

from cherrylove.identity.application.commands.account import (
    ChangePassword,
    ProfileBefore,
    ProfileChanges,
    UpdateMe,
)
from cherrylove.identity.application.queries.profile import CoupleRow, GetCoupleHeader, PersonSummary
from cherrylove.identity.domain.couple import days_together
from cherrylove.shared.domain.actor import Actor, ActorResolver, Membership
from cherrylove.shared.domain.errors import FieldError
from cherrylove.shared.domain.ids import CoupleId, UserId
from tests.fakes.audit_log import InMemoryAuditLog
from tests.fakes.clock import FixedClock
from tests.fakes.unit_of_work import InMemoryUnitOfWork

USER, COUPLE = UserId(uuid.uuid7()), CoupleId(uuid.uuid7())


class _Resolver(ActorResolver):
    def _membership_for(self, user_id: UserId) -> Membership:
        return Membership(user_id, COUPLE, "es")


ACTOR: Actor = _Resolver().resolve(USER)


@dataclass
class FakeProfiles:
    before: ProfileBefore = field(default_factory=lambda: ProfileBefore("Camila", "es", None))
    saved: list[tuple[str, str, uuid.UUID | None]] = field(default_factory=list)

    def lock(self, user_id: UserId) -> ProfileBefore:
        return self.before

    def save(self, user_id: UserId, name: str, language: str, avatar_media_id: uuid.UUID | None) -> None:
        self.saved.append((name, language, avatar_media_id))


@dataclass
class FakeForget:
    forgotten: list[UserId] = field(default_factory=list)

    def forget(self, user_id: UserId) -> None:
        self.forgotten.append(user_id)


def _update() -> tuple[UpdateMe, FakeProfiles, FakeForget, InMemoryAuditLog]:
    profiles, actors, audit = FakeProfiles(), FakeForget(), InMemoryAuditLog()
    return UpdateMe(InMemoryUnitOfWork(), profiles, actors, audit), profiles, actors, audit


@pytest.mark.req("REQ-F-ACC-04")
def test_a_language_change_is_saved_audited_and_drops_the_cached_actor() -> None:
    use_case, profiles, actors, audit = _update()
    use_case.execute(ACTOR, ProfileChanges(name="Cami", language="en"))
    assert profiles.saved == [("Cami", "en", None)]
    assert actors.forgotten == [USER]
    [event] = audit.events
    assert event.changes == {"name": {"changed": True}, "language": {"from": "es", "to": "en"}}
    assert "Cami" not in repr(event.changes), "personal data stays out of the audit"


@pytest.mark.req("REQ-F-ACC-02")
def test_nothing_changed_writes_nothing() -> None:
    use_case, profiles, actors, audit = _update()
    use_case.execute(ACTOR, ProfileChanges(name="Camila"))
    assert (profiles.saved, actors.forgotten, audit.events) == ([], [], [])


@pytest.mark.req("REQ-F-ACC-01")
def test_no_avatar_id_is_valid_before_media_exist_but_null_clears_it() -> None:
    use_case, profiles, _, _ = _update()
    with pytest.raises(FieldError) as error:
        use_case.execute(ACTOR, ProfileChanges(avatar_media_id=uuid.uuid7()))
    assert (error.value.pointer, error.value.field_code) == ("/avatar_media_id", "invalid_media")
    profiles.before = ProfileBefore("Camila", "es", uuid.uuid7())
    use_case.execute(ACTOR, ProfileChanges(avatar_media_id=None))
    assert profiles.saved == [("Camila", "es", None)]


@dataclass
class FakePasswords:
    current: str = "correct horse battery"
    set_to: list[str] = field(default_factory=list)

    def matches(self, user_id: UserId, password: str) -> bool:
        return password == self.current

    def set(self, user_id: UserId, password: str) -> None:
        self.set_to.append(password)


@dataclass
class FakeSessions:
    calls: list[tuple[str, Any]] = field(default_factory=list)

    def revoke_all(self, user_id: UserId) -> int:
        self.calls.append(("all", None))
        return 3

    def revoke_others(self, user_id: UserId, keep_session: str) -> int:
        self.calls.append(("others", keep_session))
        return 2


def _change() -> tuple[ChangePassword, FakePasswords, FakeSessions, InMemoryAuditLog]:
    passwords, sessions, audit = FakePasswords(), FakeSessions(), InMemoryAuditLog()
    return ChangePassword(InMemoryUnitOfWork(), passwords, sessions, audit), passwords, sessions, audit  # type: ignore[arg-type]


@pytest.mark.req("REQ-F-ACC-03")
def test_changing_the_password_keeps_the_current_session_only() -> None:
    use_case, passwords, sessions, audit = _change()
    use_case.execute(ACTOR, "sid-1", "correct horse battery", "a new long passphrase")
    assert (passwords.set_to, sessions.calls) == (["a new long passphrase"], [("others", "sid-1")])
    assert audit.events[0].changes["revoked_sessions"] == {"from": None, "to": 2}


@pytest.mark.req("REQ-F-ACC-03")
def test_a_token_without_sid_revokes_every_session() -> None:
    use_case, _, sessions, _ = _change()
    use_case.execute(ACTOR, None, "correct horse battery", "a new long passphrase")
    assert sessions.calls == [("all", None)]


@pytest.mark.req("REQ-F-ACC-03")
def test_a_wrong_current_password_changes_nothing() -> None:
    use_case, passwords, sessions, audit = _change()
    with pytest.raises(FieldError) as error:
        use_case.execute(ACTOR, "sid-1", "not it", "a new long passphrase")
    assert (error.value.pointer, error.value.field_code) == ("/current_password", "incorrect_password")
    assert (passwords.set_to, sessions.calls, audit.events) == ([], [], [])


@pytest.mark.req("REQ-F-HOME-01")
def test_days_together_counts_civil_days_and_is_none_without_a_start() -> None:
    assert days_together(date(2023, 2, 14), date(2026, 11, 18)) == 1373
    assert days_together(None, date(2026, 11, 18)) is None


@dataclass
class FakeProfileQuery:
    row: CoupleRow

    def me(self, couple_id: CoupleId, user_id: UserId) -> Any:
        raise NotImplementedError

    def couple(self, couple_id: CoupleId) -> CoupleRow:
        return self.row


@pytest.mark.req("REQ-F-HOME-01")
def test_the_header_counts_days_in_the_couple_time_zone() -> None:
    # 03:00 UTC on 19 Nov is still 18 Nov in Bogota (UTC-5): one day less than a UTC count.
    clock = FixedClock(datetime(2026, 11, 19, 3, 0, tzinfo=UTC))
    row = CoupleRow(COUPLE.value, (PersonSummary(USER.value, "Camila", None),), date(2026, 11, 17), "America/Bogota", 1)
    header = GetCoupleHeader(FakeProfileQuery(row), clock).execute(ACTOR)
    assert header.days_together == 1

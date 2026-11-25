"""Deactivate user with fakes (IMPL-API-001 F2.15; REQ-F-ADM-01, REQ-F-AUTH-09, ADR-005)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from cherrylove.identity.application.commands.deactivate_user import DeactivateUser
from cherrylove.shared.domain.errors import NotFound
from cherrylove.shared.domain.ids import UserId
from tests.fakes.audit_log import InMemoryAuditLog
from tests.fakes.clock import FixedClock, SequentialIdGenerator
from tests.fakes.unit_of_work import InMemoryUnitOfWork

IDS = SequentialIdGenerator(FixedClock())
USER = UserId(IDS.new())


@dataclass
class FakeAccounts:
    active: dict[UserId, bool] = field(default_factory=lambda: {USER: True})

    def deactivate(self, user_id: UserId) -> bool | None:
        if user_id not in self.active:
            return None
        was, self.active[user_id] = self.active[user_id], False
        return was


@dataclass
class FakeSessions:
    killed: list[UserId] = field(default_factory=list)

    def revoke_all(self, user_id: UserId) -> int:
        self.killed.append(user_id)
        return 2


@dataclass
class FakeActorCache:
    log: list[str]

    def forget(self, user_id: UserId) -> None:
        self.log.append(f"forget {user_id.value}")


def _use_case() -> tuple[DeactivateUser, FakeAccounts, FakeSessions, list[str], InMemoryAuditLog]:
    log: list[str] = []
    accounts, sessions, audit = FakeAccounts(), FakeSessions(), InMemoryAuditLog()
    uow = InMemoryUnitOfWork()
    return DeactivateUser(uow, accounts, sessions, FakeActorCache(log), audit), accounts, sessions, log, audit  # type: ignore[arg-type]


@pytest.mark.req("REQ-F-ADM-01")
def test_deactivating_disables_revokes_audits_and_forgets_the_actor() -> None:
    use_case, accounts, sessions, log, audit = _use_case()
    use_case.execute(USER)
    assert (accounts.active[USER], sessions.killed, log) == (False, [USER], [f"forget {USER.value}"])
    [event] = audit.events
    assert (event.action, event.actor_type, event.entity_id) == ("admin.user_deactivated", "system", USER.value)
    assert event.changes == {"is_active": {"from": True, "to": False}, "revoked_sessions": {"from": None, "to": 2}}


@pytest.mark.req("REQ-F-ADM-01")
def test_an_unknown_user_is_not_found_and_nothing_is_forgotten() -> None:
    use_case, _, sessions, log, audit = _use_case()
    with pytest.raises(NotFound):
        use_case.execute(UserId(IDS.new()))
    assert (sessions.killed, log, audit.events) == ([], [], [])

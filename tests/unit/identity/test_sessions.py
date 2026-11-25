"""Login use case with fakes (IMPL-API-001 F2.10; REQ-F-AUTH-07, REQ-F-LOG-01, ADR-004 §6, ADR-008 §2)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from cherrylove.identity.application.commands.sessions import Login, Logout, RefreshSession, RequestInfo
from cherrylove.identity.application.ports import Account, Session
from cherrylove.identity.domain.errors import CoupleArchived, InvalidCredentials
from cherrylove.shared.application.audit_log import email_fingerprint
from cherrylove.shared.domain.errors import NotAuthenticated
from cherrylove.shared.domain.ids import CoupleId, UserId
from tests.fakes.audit_log import InMemoryAuditLog
from tests.fakes.clock import FixedClock, SequentialIdGenerator
from tests.fakes.identity import FakeTokenIssuer
from tests.fakes.unit_of_work import InMemoryUnitOfWork

IDS = SequentialIdGenerator(FixedClock())
USER, COUPLE = UserId(IDS.new()), CoupleId(IDS.new())
INFO = RequestInfo(ip="203.0.113.7", client="web")
KEY = "audit-hmac-test-key"


@dataclass
class FakeCredentials:
    accounts: dict[tuple[str, str], Account] = field(default_factory=dict)

    def verify(self, email: str, password: str) -> Account | None:
        return self.accounts.get((email, password))


@dataclass
class FakeStore:
    refreshed: list[str] = field(default_factory=list)
    revoked: list[str] = field(default_factory=list)

    def rotate(self, refresh: str) -> tuple[UserId, Session]:
        self.refreshed.append(refresh)
        return USER, FakeTokenIssuer().issue(USER)

    def revoke(self, refresh: str) -> UserId | None:
        self.revoked.append(refresh)
        return USER


def _login(archived: bool = False) -> tuple[Login, InMemoryAuditLog, FakeTokenIssuer]:
    audit, issuer = InMemoryAuditLog(), FakeTokenIssuer()
    credentials = FakeCredentials({("camila@example.com", "right password"): Account(USER, COUPLE, archived)})
    return Login(InMemoryUnitOfWork(), credentials, issuer, audit, KEY), audit, issuer


@pytest.mark.req("REQ-F-AUTH-07")
def test_a_successful_login_opens_a_session_and_is_audited() -> None:
    login, audit, issuer = _login()
    session = login.execute(" Camila@Example.com", "right password", INFO)
    assert issuer.issued == [USER]
    assert session.access == f"access-{USER}"
    [event] = audit.events
    assert (event.action, event.entity_id, event.ip, dict(event.device)) == (
        "auth.login",
        USER.value,
        "203.0.113.7",
        {"client": "web"},
    )


@pytest.mark.req("REQ-F-LOG-01")
@pytest.mark.parametrize(("email", "password"), [("camila@example.com", "wrong"), ("nobody@example.com", "x")])
def test_a_failed_login_stores_the_email_hmac_never_the_email_or_password(email: str, password: str) -> None:
    login, audit, issuer = _login()
    with pytest.raises(InvalidCredentials):
        login.execute(email, password, INFO)
    assert issuer.issued == []
    [event] = audit.rejected
    assert (event.action, event.outcome) == ("auth.login_failed", "rejected")
    assert event.changes == {"email_hmac": {"from": None, "to": email_fingerprint(email, KEY)}}
    assert email not in str(event)
    assert password not in str(event.changes)


@pytest.mark.req("REQ-F-AUTH-09")
def test_an_archived_couple_cannot_log_in() -> None:
    login, audit, issuer = _login(archived=True)
    with pytest.raises(CoupleArchived):
        login.execute("camila@example.com", "right password", INFO)
    assert issuer.issued == []
    assert [e.changes for e in audit.rejected] == [{"reason": {"from": None, "to": "couple_archived"}}]


@pytest.mark.req("REQ-F-ACC-06")
def test_refresh_and_logout_need_a_token_and_are_audited() -> None:
    store, audit = FakeStore(), InMemoryAuditLog()
    with pytest.raises(NotAuthenticated):
        RefreshSession(InMemoryUnitOfWork(), store, audit).execute(None, INFO)
    RefreshSession(InMemoryUnitOfWork(), store, audit).execute("r1", INFO)
    Logout(InMemoryUnitOfWork(), store, audit).execute("r2", INFO)
    Logout(InMemoryUnitOfWork(), store, audit).execute(None, INFO)
    assert (store.refreshed, store.revoked) == (["r1"], ["r2"])
    assert [e.action for e in audit.events] == ["auth.refreshed", "auth.logout"]

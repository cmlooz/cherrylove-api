"""Bilingual invite email (IMPL-API-001 F2.7; REQ-F-AUTH-01, ADR-012 §4)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta

import pytest

from cherrylove.identity.application.commands.invites import IssueInviteToken
from cherrylove.identity.application.commands.send_invite_email import SendInviteEmail
from cherrylove.identity.domain.invite import INVITE_TTL
from cherrylove.identity.domain.invite_token import hash_token
from cherrylove.shared.domain.ids import CoupleId
from tests.fakes.clock import FixedClock, SequentialIdGenerator
from tests.fakes.identity import FixedTokens, InMemoryInvites


@dataclass
class FakeMailer:
    sent: list[tuple[str, str, str]] = field(default_factory=list)

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


def _world() -> tuple[SendInviteEmail, InMemoryInvites, FakeMailer, FixedClock, uuid.UUID]:
    clock, invites, mailer = FixedClock(), InMemoryInvites(), FakeMailer()
    ids = SequentialIdGenerator(clock)
    invite_id = ids.new()
    invites.add_pending(invite_id, CoupleId(ids.new()), 1, "camila@example.com", clock.now() + INVITE_TTL)
    use_case = SendInviteEmail(
        invites=invites,
        issue=IssueInviteToken(invites, FixedTokens(), clock),
        mailer=mailer,
        clock=clock,
        link_template="https://app.example.com/invites/{token}",
    )
    return use_case, invites, mailer, clock, invite_id


@pytest.mark.req("REQ-F-AUTH-01")
def test_one_email_spanish_first_then_english_with_a_working_link() -> None:
    use_case, invites, mailer, _, invite_id = _world()
    assert use_case.execute(invite_id) is True
    [(to, subject, body)] = mailer.sent
    assert to == "camila@example.com"
    assert subject.index("invitación") < subject.index("invitation")
    assert body.index("Te invitaron") < body.index("You have been invited")
    assert body.count("https://app.example.com/invites/token-1") == 2
    assert invites.tokens[invite_id][0] == hash_token("token-1")


@pytest.mark.req("REQ-F-AUTH-02")
def test_a_revoked_invite_sends_nothing() -> None:
    use_case, invites, mailer, _, invite_id = _world()
    invites.revoke(invite_id)
    assert use_case.execute(invite_id) is False
    assert mailer.sent == []


@pytest.mark.req("REQ-F-AUTH-02")
def test_an_expired_invite_sends_nothing() -> None:
    use_case, _, mailer, clock, invite_id = _world()
    clock.advance(INVITE_TTL + timedelta(seconds=1))
    assert use_case.execute(invite_id) is False
    assert mailer.sent == []

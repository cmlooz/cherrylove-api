"""Invite issue, resend and revoke (IMPL-API-001 F2.6; REQ-F-AUTH-02, REQ-F-ADM-02, DEC-017, ADR-004 §4)."""

from __future__ import annotations

import base64
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

import pytest

from cherrylove.identity.application.commands.create_couple import SEND_INVITE_EMAIL
from cherrylove.identity.application.commands.invites import IssueInviteToken, ResendInvite, RevokeInvite
from cherrylove.identity.domain.invite import INVITE_TTL
from cherrylove.identity.domain.invite_token import TOKEN_BYTES, hash_token
from cherrylove.identity.infrastructure.adapters.tokens import SecretsTokenGenerator
from cherrylove.shared.domain.errors import NotFound
from cherrylove.shared.domain.ids import CoupleId
from tests.fakes.audit_log import InMemoryAuditLog
from tests.fakes.clock import FixedClock, SequentialIdGenerator
from tests.fakes.identity import FixedTokens, InMemoryInvites
from tests.fakes.job_queue import InMemoryJobQueue
from tests.fakes.unit_of_work import InMemoryUnitOfWork


@dataclass
class World:
    clock: FixedClock = field(default_factory=FixedClock)
    invites: InMemoryInvites = field(default_factory=InMemoryInvites)
    jobs: InMemoryJobQueue = field(default_factory=InMemoryJobQueue)
    audit: InMemoryAuditLog = field(default_factory=InMemoryAuditLog)

    def __post_init__(self) -> None:
        self.ids = SequentialIdGenerator(self.clock)
        self.couple = CoupleId(self.ids.new())
        self.first: uuid.UUID = self.ids.new()
        self.invites.add_pending(self.first, self.couple, 1, "camila@example.com", self.clock.now() + INVITE_TTL)

    def resend(self) -> ResendInvite:
        return ResendInvite(InMemoryUnitOfWork(), self.clock, self.ids, self.invites, self.jobs, self.audit)

    def revoke(self) -> RevokeInvite:
        return RevokeInvite(InMemoryUnitOfWork(), self.invites, self.audit)


@pytest.mark.req("REQ-F-AUTH-02")
def test_real_tokens_carry_32_random_bytes() -> None:
    token = SecretsTokenGenerator().new()
    assert len(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))) == TOKEN_BYTES
    assert token != SecretsTokenGenerator().new()


@pytest.mark.req("REQ-F-AUTH-02")
def test_issuing_stores_only_the_sha256_and_returns_the_raw_token() -> None:
    world = World()
    raw = IssueInviteToken(world.invites, FixedTokens(), world.clock).execute(world.first)
    stored, sent_at = world.invites.tokens[world.first]
    assert stored == hashlib.sha256(raw.encode()).digest() == hash_token(raw)
    assert raw.encode() not in stored
    assert sent_at == world.clock.now()


@pytest.mark.req("REQ-F-AUTH-02")
def test_a_non_pending_invite_gets_no_token() -> None:
    world = World()
    world.invites.revoke(world.first)
    with pytest.raises(NotFound):
        IssueInviteToken(world.invites, FixedTokens(), world.clock).execute(world.first)


@pytest.mark.req("REQ-F-ADM-02")
def test_resend_revokes_the_old_invite_and_issues_a_new_one_for_72_hours() -> None:
    world = World()
    world.clock.advance(timedelta(hours=50))
    new_id = world.resend().execute(world.couple, 1)

    assert world.invites.status[world.first] == "revoked"
    renewed = world.invites.get(new_id)
    assert renewed is not None
    assert (renewed.status, renewed.email) == ("pending", "camila@example.com")
    assert renewed.expires_at == world.clock.now() + INVITE_TTL
    assert [(j.job, j.idempotency_key) for j in world.jobs.jobs] == [(SEND_INVITE_EMAIL, f"email:invite:{new_id}")]
    assert [e.action for e in world.audit.events] == ["invite.resent"]


@pytest.mark.req("REQ-F-ADM-02")
def test_resend_without_a_pending_invite_is_not_found() -> None:
    world = World()
    with pytest.raises(NotFound):
        world.resend().execute(world.couple, 2)


@pytest.mark.req("REQ-F-ADM-02")
def test_revoke_kills_a_pending_invite_once() -> None:
    world = World()
    world.revoke().execute(world.first)
    assert world.invites.status[world.first] == "revoked"
    assert [e.action for e in world.audit.events] == ["invite.revoked"]
    with pytest.raises(NotFound):
        world.revoke().execute(world.first)

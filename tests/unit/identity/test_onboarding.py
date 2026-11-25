"""Open and accept an invite with fakes (IMPL-API-001 F2.8; REQ-F-AUTH-02…06, DEC-017, DEC-018)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta

import pytest

from cherrylove.identity.application.commands.onboarding import AcceptInvite, GetInvite, Onboarding
from cherrylove.identity.application.ports import InviteContext
from cherrylove.identity.domain.errors import CoupleArchived, CoupleFull, InviteExpired, InviteRevoked
from cherrylove.identity.domain.invite import INVITE_TTL, InviteSnapshot
from cherrylove.identity.domain.invite_token import hash_token
from cherrylove.shared.domain.errors import DomainError, NotFound
from cherrylove.shared.domain.ids import CoupleId
from tests.fakes.audit_log import InMemoryAuditLog
from tests.fakes.clock import FixedClock, SequentialIdGenerator
from tests.fakes.identity import FakeTokenIssuer, InMemoryInviteLookup, InMemoryPartners
from tests.fakes.unit_of_work import InMemoryUnitOfWork

TOKEN = "raw-token"
ONBOARDING = Onboarding(name="Camila", birth_date=date(1996, 3, 9), password="correct horse battery")


@dataclass
class World:
    clock: FixedClock = field(default_factory=FixedClock)
    lookup: InMemoryInviteLookup = field(default_factory=InMemoryInviteLookup)
    partners: InMemoryPartners = field(default_factory=InMemoryPartners)
    sessions: FakeTokenIssuer = field(default_factory=FakeTokenIssuer)
    audit: InMemoryAuditLog = field(default_factory=InMemoryAuditLog)

    def __post_init__(self) -> None:
        self.ids = SequentialIdGenerator(self.clock)
        self.couple = CoupleId(self.ids.new())
        invite = InviteSnapshot(
            self.ids.new(), self.couple, 1, "camila@example.com", "pending", self.clock.now() + INVITE_TTL
        )
        self.context = InviteContext(invite, couple_archived=False, seat_taken=False, relationship_start=None)
        self.lookup.by_hash[hash_token(TOKEN)] = self.context

    def set_context(self, context: InviteContext) -> None:
        self.lookup.by_hash[hash_token(TOKEN)] = context

    def accept(self) -> AcceptInvite:
        uow = InMemoryUnitOfWork()
        return AcceptInvite(uow, self.clock, self.ids, self.lookup, self.partners, self.sessions, self.audit)


@pytest.mark.req("REQ-F-AUTH-02")
def test_a_usable_invite_previews_email_and_whether_the_date_is_known() -> None:
    world = World()
    preview = GetInvite(world.lookup, world.clock).execute(TOKEN)
    assert (preview.email, preview.relationship_start_known) == ("camila@example.com", False)


@pytest.mark.req("REQ-F-AUTH-02")
@pytest.mark.parametrize(
    ("change", "error"),
    [
        (lambda c: None, NotFound),
        (lambda c: replace(c, invite=replace(c.invite, status="accepted")), NotFound),
        (lambda c: replace(c, invite=replace(c.invite, status="revoked")), InviteRevoked),
        (lambda c: replace(c, invite=replace(c.invite, status="expired")), InviteExpired),
        (lambda c: replace(c, couple_archived=True), CoupleArchived),
        (lambda c: replace(c, seat_taken=True), CoupleFull),
    ],
    ids=["unknown", "already-accepted", "revoked", "expired", "archived", "seat-taken"],
)
def test_an_unusable_invite_raises_its_contract_code(change: object, error: type[DomainError]) -> None:
    world = World()
    changed = change(world.context)  # type: ignore[operator]
    if changed is None:
        world.lookup.by_hash.clear()
    else:
        world.set_context(changed)
    with pytest.raises(error):
        GetInvite(world.lookup, world.clock).execute(TOKEN)
    with pytest.raises(error):
        world.accept().execute(TOKEN, ONBOARDING)
    assert world.partners.added == []


@pytest.mark.req("REQ-F-AUTH-02")
def test_a_pending_invite_past_72_hours_is_expired() -> None:
    world = World()
    world.clock.advance(INVITE_TTL + timedelta(seconds=1))
    with pytest.raises(InviteExpired):
        GetInvite(world.lookup, world.clock).execute(TOKEN)


@pytest.mark.req("REQ-F-AUTH-04")
def test_the_first_partner_sets_the_relationship_start_and_can_use_the_app_alone() -> None:
    world = World()
    session = world.accept().execute(TOKEN, replace(ONBOARDING, relationship_start=date(2023, 2, 14)))
    [(user_id, partner, couple, slot)] = world.partners.added
    assert (partner.email, partner.name, couple, slot) == ("camila@example.com", "Camila", world.couple, 1)
    assert world.partners.relationship_starts == {world.couple: date(2023, 2, 14)}
    assert world.partners.accepted == [world.context.invite.invite_id]
    assert world.sessions.issued == [user_id]
    assert session.access == f"access-{user_id}"
    assert [e.action for e in world.audit.events] == ["invite.accepted"]


@pytest.mark.req("REQ-F-AUTH-04")
def test_the_second_partner_is_not_asked_the_date_and_cannot_change_it() -> None:
    world = World()
    world.set_context(replace(world.context, relationship_start=date(2023, 2, 14)))
    assert GetInvite(world.lookup, world.clock).execute(TOKEN).relationship_start_known is True
    world.accept().execute(TOKEN, replace(ONBOARDING, relationship_start=date(2020, 1, 1)))
    assert world.partners.relationship_starts == {}

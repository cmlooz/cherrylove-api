"""Open and accept an invite (REQ-F-AUTH-02…06, REQ-F-AUTH-10, DEC-017, DEC-018).

A token is usable only while its invite is pending, unexpired, its couple active and its seat free. An
accepted invite answers like an unknown token (single use: it reveals nothing). Accepting creates the
partner's account and membership, marks the invite accepted and opens a session: the first partner already
can use the app alone (DEC-018). Only the first partner sets the relationship start; for the second the
date is already known and any value sent is ignored (REQ-F-AUTH-04).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from cherrylove.identity.application.ports import (
    InviteContext,
    InviteLookup,
    NewPartner,
    PartnerRepository,
    Session,
    TokenIssuer,
)
from cherrylove.identity.domain.errors import CoupleArchived, CoupleFull, InviteExpired, InviteRevoked
from cherrylove.identity.domain.invite_token import hash_token
from cherrylove.shared.application.audit_log import AuditEvent, AuditLog
from cherrylove.shared.application.unit_of_work import UnitOfWork
from cherrylove.shared.domain.clock import Clock
from cherrylove.shared.domain.errors import NotFound
from cherrylove.shared.domain.ids import IdGenerator, UserId


@dataclass(frozen=True, slots=True)
class InvitePreview:
    email: str
    relationship_start_known: bool


@dataclass(frozen=True, slots=True)
class Onboarding:
    name: str
    birth_date: date
    password: str
    relationship_start: date | None = None
    language: str = "es"


def usable_invite(lookup: InviteLookup, clock: Clock, token: str) -> InviteContext:
    """Guard clauses in the order a person would hit them; raises the contract code for each."""
    context = lookup.by_token_hash(hash_token(token))
    if context is None or context.invite.status == "accepted":
        raise NotFound("unknown invite")
    if context.invite.status == "revoked":
        raise InviteRevoked("the invite was revoked")
    if context.invite.status == "expired" or context.invite.expires_at <= clock.now():
        raise InviteExpired("the invite expired")
    if context.couple_archived:
        raise CoupleArchived("the couple is archived")
    if context.seat_taken:
        raise CoupleFull("the seat is already taken")
    return context


@dataclass(frozen=True, slots=True)
class GetInvite:
    lookup: InviteLookup
    clock: Clock

    def execute(self, token: str) -> InvitePreview:
        context = usable_invite(self.lookup, self.clock, token)
        return InvitePreview(context.invite.email, context.relationship_start is not None)


@dataclass(frozen=True, slots=True)
class AcceptInvite:
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator
    lookup: InviteLookup
    partners: PartnerRepository
    sessions: TokenIssuer
    audit: AuditLog

    def execute(self, token: str, onboarding: Onboarding) -> Session:
        context = usable_invite(self.lookup, self.clock, token)
        invite = context.invite
        user_id = UserId(self.ids.new())
        partner = NewPartner(
            invite.email, onboarding.name, onboarding.birth_date, onboarding.password, onboarding.language
        )
        with self.uow.atomic():
            self.partners.add(user_id, partner, invite.couple_id, invite.slot)
            self.partners.accept_invite(invite.invite_id, self.clock.now())
            if context.relationship_start is None and onboarding.relationship_start is not None:
                self.partners.set_relationship_start(invite.couple_id, onboarding.relationship_start)
            self.audit.record(
                AuditEvent(
                    action="invite.accepted",
                    actor_type="anonymous",
                    entity_type="invite",
                    entity_id=invite.invite_id,
                    changes={"slot": {"from": None, "to": invite.slot}},
                )
            )
            session = self.sessions.issue(user_id)
        return session

"""In-memory fakes of the identity ports (ADR-014 §1)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from cherrylove.identity.application.ports import InviteContext, NewPartner, Session
from cherrylove.identity.domain.invite import InviteSnapshot, Slot
from cherrylove.shared.domain.ids import CoupleId, UserId


@dataclass
class InMemoryMemberships:
    emails: set[str] = field(default_factory=set)

    def emails_in_a_couple(self, emails: Iterable[str]) -> set[str]:
        return self.emails & set(emails)


@dataclass
class InMemoryCouples:
    added: list[CoupleId] = field(default_factory=list)

    def add(self, couple_id: CoupleId) -> None:
        self.added.append(couple_id)


@dataclass(frozen=True)
class PendingInvite:
    invite_id: uuid.UUID
    couple_id: CoupleId
    slot: Slot
    email: str
    expires_at: datetime


@dataclass
class InMemoryInvites:
    pending: list[PendingInvite] = field(default_factory=list)
    status: dict[uuid.UUID, str] = field(default_factory=dict)
    tokens: dict[uuid.UUID, tuple[bytes, datetime]] = field(default_factory=dict)

    def add_pending(
        self, invite_id: uuid.UUID, couple_id: CoupleId, slot: Slot, email: str, expires_at: datetime
    ) -> None:
        self.pending.append(PendingInvite(invite_id, couple_id, slot, email, expires_at))
        self.status[invite_id] = "pending"

    def get(self, invite_id: uuid.UUID) -> InviteSnapshot | None:
        for invite in self.pending:
            if invite.invite_id == invite_id:
                return InviteSnapshot(
                    invite.invite_id, invite.couple_id, invite.slot, invite.email,
                    self.status[invite_id], invite.expires_at,  # type: ignore[arg-type]
                )  # fmt: skip
        return None

    def pending_for_seat(self, couple_id: CoupleId, slot: Slot) -> InviteSnapshot | None:
        for invite in self.pending:
            if (invite.couple_id, invite.slot, self.status[invite.invite_id]) == (couple_id, slot, "pending"):
                return self.get(invite.invite_id)
        return None

    def revoke(self, invite_id: uuid.UUID) -> None:
        if self.status.get(invite_id) == "pending":
            self.status[invite_id] = "revoked"

    def set_token(self, invite_id: uuid.UUID, token_hash: bytes, sent_at: datetime) -> None:
        self.tokens[invite_id] = (token_hash, sent_at)


@dataclass
class FixedTokens:
    issued: list[str] = field(default_factory=list)

    def new(self) -> str:
        token = f"token-{len(self.issued) + 1}"
        self.issued.append(token)
        return token


@dataclass
class RecordingProvisioner:
    provisioned: list[CoupleId] = field(default_factory=list)

    def provision(self, couple_id: CoupleId) -> None:
        self.provisioned.append(couple_id)


@dataclass
class InMemoryInviteLookup:
    by_hash: dict[bytes, InviteContext] = field(default_factory=dict)

    def by_token_hash(self, token_hash: bytes) -> InviteContext | None:
        return self.by_hash.get(token_hash)


@dataclass
class InMemoryPartners:
    added: list[tuple[UserId, NewPartner, CoupleId, Slot]] = field(default_factory=list)
    accepted: list[uuid.UUID] = field(default_factory=list)
    relationship_starts: dict[CoupleId, date] = field(default_factory=dict)

    def add(self, user_id: UserId, partner: NewPartner, couple_id: CoupleId, slot: Slot) -> None:
        self.added.append((user_id, partner, couple_id, slot))

    def accept_invite(self, invite_id: uuid.UUID, accepted_at: datetime) -> None:
        self.accepted.append(invite_id)

    def set_relationship_start(self, couple_id: CoupleId, relationship_start: date) -> None:
        self.relationship_starts.setdefault(couple_id, relationship_start)


@dataclass
class FakeTokenIssuer:
    issued: list[UserId] = field(default_factory=list)

    def issue(self, user_id: UserId) -> Session:
        self.issued.append(user_id)
        now = datetime(2026, 11, 18, 14, 0)
        return Session(f"access-{user_id}", now + timedelta(minutes=10), f"refresh-{user_id}", now + timedelta(days=30))

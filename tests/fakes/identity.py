"""In-memory fakes of the identity ports (ADR-014 §1)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from cherrylove.identity.domain.invite import InviteSnapshot, Slot
from cherrylove.shared.domain.ids import CoupleId


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

"""In-memory fakes of the identity ports (ADR-014 §1)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from cherrylove.identity.domain.invite import Slot
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

    def add_pending(
        self, invite_id: uuid.UUID, couple_id: CoupleId, slot: Slot, email: str, expires_at: datetime
    ) -> None:
        self.pending.append(PendingInvite(invite_id, couple_id, slot, email, expires_at))


@dataclass
class RecordingProvisioner:
    provisioned: list[CoupleId] = field(default_factory=list)

    def provision(self, couple_id: CoupleId) -> None:
        self.provisioned.append(couple_id)

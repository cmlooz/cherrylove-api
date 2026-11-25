"""My account and the couple header (REQ-F-ACC-02, REQ-F-HOME-01): read side, DTOs only (CQRS-lite)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from zoneinfo import ZoneInfo

from cherrylove.identity.domain.couple import days_together
from cherrylove.shared.domain.actor import Actor
from cherrylove.shared.domain.clock import Clock
from cherrylove.shared.domain.ids import CoupleId, UserId


@dataclass(frozen=True, slots=True)
class PersonSummary:
    id: uuid.UUID
    name: str
    avatar_media_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class MeView:
    id: uuid.UUID
    email: str
    name: str
    birth_date: date | None
    language: str
    avatar_media_id: uuid.UUID | None
    partner: PersonSummary | None


@dataclass(frozen=True, slots=True)
class CoupleRow:
    id: uuid.UUID
    partners: tuple[PersonSummary, ...]
    relationship_start: date | None
    timezone: str
    version: int


@dataclass(frozen=True, slots=True)
class CoupleHeader:
    id: uuid.UUID
    partners: tuple[PersonSummary, ...]
    relationship_start: date | None
    days_together: int | None
    timezone: str
    version: int


class ProfileQuery(Protocol):
    def me(self, couple_id: CoupleId, user_id: UserId) -> MeView: ...

    def couple(self, couple_id: CoupleId) -> CoupleRow:
        """Partners in slot order."""
        ...


@dataclass(frozen=True, slots=True)
class GetMe:
    profiles: ProfileQuery

    def execute(self, actor: Actor) -> MeView:
        return self.profiles.me(actor.couple_id, actor.user_id)


@dataclass(frozen=True, slots=True)
class GetCoupleHeader:
    profiles: ProfileQuery
    clock: Clock

    def execute(self, actor: Actor) -> CoupleHeader:
        row = self.profiles.couple(actor.couple_id)
        today = self.clock.now().astimezone(ZoneInfo(row.timezone)).date()
        return CoupleHeader(
            row.id,
            row.partners,
            row.relationship_start,
            days_together(row.relationship_start, today),
            row.timezone,
            row.version,
        )

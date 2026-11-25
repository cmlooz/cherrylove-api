"""Invite rules (DEC-017, ADR-004 §4): 72 hours, one live invite per seat, single use."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from cherrylove.shared.domain.ids import CoupleId

INVITE_TTL = timedelta(hours=72)

type Slot = Literal[1, 2]
type InviteStatus = Literal["pending", "accepted", "revoked", "expired"]


@dataclass(frozen=True, slots=True)
class InviteSnapshot:
    invite_id: uuid.UUID
    couple_id: CoupleId
    slot: Slot
    email: str
    status: InviteStatus
    expires_at: datetime


def normalize_email(email: str) -> str:
    return email.strip().lower()


def invite_expires_at(now: datetime) -> datetime:
    return now + INVITE_TTL

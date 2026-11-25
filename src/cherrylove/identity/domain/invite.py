"""Invite rules (DEC-017, ADR-004 §4): 72 hours, one live invite per seat, single use."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

INVITE_TTL = timedelta(hours=72)

type Slot = Literal[1, 2]


def normalize_email(email: str) -> str:
    return email.strip().lower()


def invite_expires_at(now: datetime) -> datetime:
    return now + INVITE_TTL

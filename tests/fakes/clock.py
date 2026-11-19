"""In-memory fakes for the time and ID ports (ADR-014 §4)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

DEFAULT_NOW = datetime(2026, 11, 18, 14, 0, tzinfo=UTC)


@dataclass
class FixedClock:
    current: datetime = DEFAULT_NOW

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


def uuid7_at(instant: datetime, tail: int = 0) -> uuid.UUID:
    """A valid UUIDv7 whose timestamp is `instant` (deterministic for a given tail)."""
    millis = int(instant.timestamp() * 1000)
    rand_a = tail & 0xFFF
    rand_b = (tail >> 12) & ((1 << 62) - 1)
    value = (millis << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return uuid.UUID(int=value)


@dataclass
class SequentialIdGenerator:
    clock: FixedClock = field(default_factory=FixedClock)
    counter: int = 0

    def new(self) -> uuid.UUID:
        self.counter += 1
        return uuid7_at(self.clock.now(), self.counter)

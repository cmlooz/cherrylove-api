"""Client-generated UUIDv7 identifiers (ADR-006 §8, REQ-F-SYNC-03).

The server accepts an ID only if its version nibble is 7 and its embedded timestamp is at most 24 h ahead
of the server clock. Typed wrappers (`CoupleId`, `UserId`, ...) keep IDs of different entities apart.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, Self

from cherrylove.shared.domain.clock import Clock
from cherrylove.shared.domain.errors import FieldError

MAX_CLOCK_SKEW = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class Uuid7:
    value: uuid.UUID

    @classmethod
    def parse(cls, raw: str | uuid.UUID, clock: Clock, pointer: str = "/id") -> Self:
        if isinstance(raw, str):
            try:
                raw = uuid.UUID(raw)
            except ValueError:
                raise FieldError(pointer, "invalid_format") from None
        if raw.version != 7:
            raise FieldError(pointer, "invalid_uuid_version")
        if timestamp_of(raw) > clock.now() + MAX_CLOCK_SKEW:
            raise FieldError(pointer, "timestamp_too_far_ahead", max_hours=24)
        return cls(raw)

    def __str__(self) -> str:
        return str(self.value)


def timestamp_of(value: uuid.UUID) -> datetime:
    """The 48-bit Unix-milliseconds prefix of a UUIDv7 (RFC 9562 §5.7)."""
    return datetime.fromtimestamp((value.int >> 80) / 1000, tz=UTC)


class CoupleId(Uuid7):
    __slots__ = ()


class UserId(Uuid7):
    __slots__ = ()


class IdGenerator(Protocol):
    """Injectable source of new UUIDv7 values (ADR-014 §4)."""

    def new(self) -> uuid.UUID: ...

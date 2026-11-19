"""Keyset pagination types (REQ-N-PERF-02, ADR-003 §5): `{results, next_cursor}` with an opaque cursor.

Query services receive a `PageRequest` (the decoded keyset position of the last row seen, or None for the
first page) and return a `Page` whose `next_position` the HTTP layer encodes into `next_cursor`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

DEFAULT_LIMIT = 50
MAX_LIMIT = 500

type Position = Mapping[str, str | int]


@dataclass(frozen=True, slots=True)
class PageRequest:
    position: Position | None
    limit: int = DEFAULT_LIMIT


@dataclass(frozen=True, slots=True)
class Page[T]:
    results: Sequence[T]
    next_position: Position | None

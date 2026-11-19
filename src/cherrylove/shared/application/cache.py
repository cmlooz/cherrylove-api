"""Cache port, cache-aside (ADR-011 §1, REQ-N-PERF-04).

Values are JSON-serializable references (IDs, ordering), never content: hydration happens after the hit.
Keys are versioned (`...:{seq}`) instead of invalidated; every key also expires within 24 h as a safety net.
A cache outage never changes an answer: adapters fail open (ADR-011 §2).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta
from typing import Protocol

SAFETY_TTL = timedelta(hours=24)

# Covariant containers, so list[str] or dict[str, int] are Cacheable.
type Cacheable = bool | int | float | str | Sequence[Cacheable] | Mapping[str, Cacheable] | None


def effective_ttl(ttl: timedelta | None) -> timedelta:
    return SAFETY_TTL if ttl is None else min(ttl, SAFETY_TTL)


class Cache(Protocol):
    def get_or_compute[T: Cacheable](self, key: str, compute: Callable[[], T], ttl: timedelta | None = None) -> T:
        """Return the cached value or compute, store and return it."""
        ...

    def delete(self, key: str) -> None:
        """Explicit invalidation, e.g. `actor:{user_id}` on archive or disable (ADR-011 §1)."""
        ...

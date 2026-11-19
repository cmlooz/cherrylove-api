"""Production adapters for the time and ID ports (ADR-014 §4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(tz=UTC)


class Uuid7Generator:
    """Stdlib `uuid.uuid7()` (Python 3.14, ADR-016 §2): no helper, no dependency."""

    def new(self) -> uuid.UUID:
        return uuid.uuid7()

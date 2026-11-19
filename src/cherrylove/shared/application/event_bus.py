"""Event bus port (ADR-001 §3-4).

Events are delivered **after commit** and may be lost on a crash (notifications, favorites cleanup can be
re-derived). Anything that must never be lost (audit, sync changes, jobs) goes through its own port inside
the unit of work instead.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from cherrylove.shared.domain.events import DomainEvent

type Handler[E: DomainEvent] = Callable[[E], None]


class EventBus(Protocol):
    def publish(self, event: DomainEvent) -> None:
        """Deliver `event` to its handlers once the current unit of work commits; never after a rollback."""
        ...

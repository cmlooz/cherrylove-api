"""In-process event bus dispatched through the unit of work after-commit hook (ADR-001 §3-4)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from cherrylove.shared.application.event_bus import Handler
from cherrylove.shared.application.unit_of_work import UnitOfWork
from cherrylove.shared.domain.events import DomainEvent


class InProcessEventBus:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._handlers: defaultdict[type[DomainEvent], list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe[E: DomainEvent](self, event_type: type[E], handler: Handler[E]) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        # One robust callback per handler: a failing handler never stops the others.
        for handler in self._handlers[type(event)]:
            self._uow.on_commit(_bind(handler, event))


def _bind(handler: Callable[[Any], None], event: DomainEvent) -> Callable[[], None]:
    return lambda: handler(event)

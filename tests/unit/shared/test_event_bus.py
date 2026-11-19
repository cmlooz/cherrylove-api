"""After-commit event bus (IMPL-API-001 F1.4, ADR-001 §3-4), on the in-memory unit of work."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from cherrylove.shared.application.event_bus import EventBus
from cherrylove.shared.domain.events import DomainEvent
from cherrylove.shared.infrastructure.in_process_event_bus import InProcessEventBus
from tests.fakes.unit_of_work import InMemoryUnitOfWork


@dataclass(frozen=True, slots=True, kw_only=True)
class NoteHidden(DomainEvent):
    note_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CardPublished(DomainEvent):
    card_id: str


class Boom(Exception):
    pass


def _port(bus: InProcessEventBus) -> EventBus:
    return bus


@pytest.mark.req("REQ-N-ARC-01")
def test_handlers_run_after_commit_with_their_event_type_only() -> None:
    uow = InMemoryUnitOfWork()
    bus = InProcessEventBus(uow)
    seen: list[str] = []
    bus.subscribe(NoteHidden, lambda event: seen.append(f"hidden:{event.note_id}"))
    bus.subscribe(CardPublished, lambda event: seen.append(f"card:{event.card_id}"))
    with uow.atomic():
        _port(bus).publish(NoteHidden(note_id="n1"))
        assert seen == []
    assert seen == ["hidden:n1"]


@pytest.mark.req("REQ-N-ARC-01")
def test_handlers_never_run_after_rollback() -> None:
    uow = InMemoryUnitOfWork()
    bus = InProcessEventBus(uow)
    seen: list[str] = []
    bus.subscribe(NoteHidden, lambda event: seen.append(event.note_id))
    with pytest.raises(Boom), uow.atomic():
        bus.publish(NoteHidden(note_id="n1"))
        raise Boom
    assert seen == []


@pytest.mark.req("REQ-N-ARC-01")
def test_a_failing_handler_does_not_stop_the_others() -> None:
    uow = InMemoryUnitOfWork()
    bus = InProcessEventBus(uow)
    seen: list[str] = []

    def failing(event: NoteHidden) -> None:
        raise Boom

    bus.subscribe(NoteHidden, failing)
    bus.subscribe(NoteHidden, lambda event: seen.append(event.note_id))
    with uow.atomic():
        bus.publish(NoteHidden(note_id="n1"))
    assert seen == ["n1"]


@pytest.mark.req("REQ-N-ARC-01")
def test_an_event_without_handlers_is_a_no_op() -> None:
    uow = InMemoryUnitOfWork()
    with uow.atomic():
        InProcessEventBus(uow).publish(CardPublished(card_id="c1"))
    assert uow.commits == 1

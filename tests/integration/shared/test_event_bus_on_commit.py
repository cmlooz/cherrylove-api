"""On PostgreSQL: handlers run after commit, never after rollback (IMPL-API-001 F1.4, ADR-001 §3-4)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from cherrylove.shared.domain.events import DomainEvent
from cherrylove.shared.infrastructure.django_unit_of_work import DjangoUnitOfWork
from cherrylove.shared.infrastructure.in_process_event_bus import InProcessEventBus

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True, kw_only=True)
class Probe(DomainEvent):
    value: int


class Boom(Exception):
    pass


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.django_db(transaction=True)
def test_handler_runs_after_commit_never_after_rollback() -> None:
    uow = DjangoUnitOfWork()
    bus = InProcessEventBus(uow)
    seen: list[int] = []
    bus.subscribe(Probe, lambda event: seen.append(event.value))

    with uow.atomic():
        bus.publish(Probe(value=1))
        assert seen == []
    assert seen == [1]

    with pytest.raises(Boom), uow.atomic():
        bus.publish(Probe(value=2))
        raise Boom
    assert seen == [1]

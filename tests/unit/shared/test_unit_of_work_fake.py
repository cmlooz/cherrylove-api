"""The in-memory UnitOfWork behaves like Django's (IMPL-API-001 F1.3, ADR-001 §5)."""

from __future__ import annotations

import pytest

from cherrylove.shared.application.unit_of_work import UnitOfWork
from tests.fakes.unit_of_work import InMemoryUnitOfWork


class Boom(Exception):
    pass


def _port(uow: UnitOfWork) -> UnitOfWork:
    return uow


@pytest.mark.req("REQ-N-ARC-01")
def test_callbacks_run_once_after_the_outermost_commit() -> None:
    uow, ran = InMemoryUnitOfWork(), []
    with _port(uow).atomic():
        uow.on_commit(lambda: ran.append("outer"))
        with uow.atomic():
            uow.on_commit(lambda: ran.append("inner"))
        assert ran == []
    assert ran == ["outer", "inner"]
    assert (uow.commits, uow.rollbacks) == (1, 0)


@pytest.mark.req("REQ-N-ARC-01")
def test_rollback_discards_callbacks_and_propagates() -> None:
    uow, ran = InMemoryUnitOfWork(), []
    with pytest.raises(Boom), uow.atomic():
        uow.on_commit(lambda: ran.append("never"))
        raise Boom
    assert ran == []
    assert (uow.commits, uow.rollbacks) == (0, 1)


@pytest.mark.req("REQ-N-ARC-01")
def test_inner_savepoint_rollback_keeps_outer_callbacks() -> None:
    uow, ran = InMemoryUnitOfWork(), []
    with uow.atomic():
        uow.on_commit(lambda: ran.append("outer"))
        with pytest.raises(Boom), uow.atomic():
            uow.on_commit(lambda: ran.append("inner"))
            raise Boom
    assert ran == ["outer"]


@pytest.mark.req("REQ-N-ARC-01")
def test_outside_a_transaction_callbacks_run_at_once_and_failures_are_contained() -> None:
    uow, ran = InMemoryUnitOfWork(), []

    def failing() -> None:
        raise Boom

    uow.on_commit(failing)
    uow.on_commit(lambda: ran.append("now"))
    assert ran == ["now"]

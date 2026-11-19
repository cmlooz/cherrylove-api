"""Django UnitOfWork on real PostgreSQL: an exception inside leaves no row (IMPL-API-001 F1.3, ADR-001 §5)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from django.db import connections

from cherrylove.shared.infrastructure.django_unit_of_work import DjangoUnitOfWork

pytestmark = pytest.mark.integration


class Boom(Exception):
    pass


@pytest.fixture
def probe() -> Iterator[str]:
    name = f"uow_probe_{uuid.uuid4().hex[:8]}"
    with connections["maintenance"].cursor() as cursor:
        cursor.execute(f"CREATE TABLE {name} (note text)")
    yield name
    with connections["maintenance"].cursor() as cursor:
        cursor.execute(f"DROP TABLE {name}")


def _count(table: str) -> int:
    with connections["default"].cursor() as cursor:
        cursor.execute(f"SELECT count(*) FROM {table}")
        row = cursor.fetchone()
    assert row is not None
    return int(row[0])


def _insert(table: str, note: str) -> None:
    with connections["default"].cursor() as cursor:
        cursor.execute(f"INSERT INTO {table} (note) VALUES (%s)", [note])


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.django_db(databases=["default", "maintenance"], transaction=True)
def test_exception_inside_the_unit_of_work_leaves_no_row(probe: str) -> None:
    uow = DjangoUnitOfWork()
    with pytest.raises(Boom), uow.atomic():
        _insert(probe, "first")
        _insert(probe, "second")
        raise Boom
    assert _count(probe) == 0


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.django_db(databases=["default", "maintenance"], transaction=True)
def test_success_commits_every_row_and_then_runs_callbacks(probe: str) -> None:
    uow, seen = DjangoUnitOfWork(), []
    with uow.atomic():
        _insert(probe, "first")
        uow.on_commit(lambda: seen.append(_count(probe)))
        assert seen == []
    assert seen == [1]

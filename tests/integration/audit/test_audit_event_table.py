"""Partitioned, append-only audit_event (IMPL-API-001 F1.11; ADR-008 §1, §4, §5; REQ-F-LOG-03/04)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import DatabaseError, ProgrammingError, connections, transaction

pytestmark = pytest.mark.integration
DBS = ["default", "maintenance"]


def _rows(alias: str, sql: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    with connections[alias].cursor() as cursor:
        cursor.execute(sql, params or [])
        return list(cursor.fetchall())


def _month_names(count: int) -> list[str]:
    now = datetime.now(tz=UTC)
    names = []
    for offset in range(count):
        year, month = divmod(now.month - 1 + offset, 12)
        names.append(f"audit_event_y{now.year + year}m{month + 1:02d}")
    return names


def _partitions() -> list[str]:
    rows = _rows(
        "maintenance",
        "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid "
        "WHERE i.inhparent = 'audit_event'::regclass ORDER BY c.relname",
    )
    return [str(row[0]) for row in rows]


@pytest.fixture
def event_id() -> uuid.UUID:
    """One committed row inserted by the app role (the table never lets anyone delete it)."""
    value = uuid.uuid7()
    with connections["default"].cursor() as cursor:
        cursor.execute(
            "INSERT INTO audit_event (id, occurred_at, actor_type, action, outcome) "
            "VALUES (%s, now(), 'system', 'probe.created', 'success')",
            [value],
        )
    return value


@pytest.mark.req("REQ-F-LOG-04")
@pytest.mark.django_db(databases=DBS)
def test_current_month_and_three_ahead_exist() -> None:
    assert set(_month_names(4)) <= set(_partitions())


@pytest.mark.req("REQ-F-LOG-04")
@pytest.mark.django_db(databases=DBS)
def test_ensuring_partitions_is_idempotent() -> None:
    before = _partitions()
    _rows("maintenance", "SELECT audit_ensure_partitions(3)")
    assert _partitions() == before


@pytest.mark.req("REQ-F-LOG-04")
@pytest.mark.django_db(databases=DBS)
def test_every_partition_has_its_own_indexes() -> None:
    for partition in _partitions():
        definitions = [
            str(row[0])
            for row in _rows("maintenance", "SELECT indexdef FROM pg_indexes WHERE tablename = %s", [partition])
        ]
        for columns in (
            "(couple_id, occurred_at)",
            "(actor_id, occurred_at)",
            "(action, occurred_at)",
            "(id, occurred_at)",
        ):
            assert any(columns in definition for definition in definitions), (partition, columns)


@pytest.mark.req("REQ-F-LOG-03")
@pytest.mark.django_db(databases=DBS, transaction=True)
def test_app_role_inserts_and_reads(event_id: uuid.UUID) -> None:
    assert _rows("default", "SELECT action FROM audit_event WHERE id = %s", [event_id]) == [("probe.created",)]


@pytest.mark.req("REQ-F-LOG-03")
@pytest.mark.django_db(databases=DBS, transaction=True)
@pytest.mark.parametrize(
    "statement", ["UPDATE audit_event SET outcome = 'failed' WHERE id = %s", "DELETE FROM audit_event WHERE id = %s"]
)
def test_app_role_update_and_delete_are_denied(event_id: uuid.UUID, statement: str) -> None:
    with pytest.raises(ProgrammingError, match="permission denied"), transaction.atomic(using="default"):
        _rows("default", statement, [event_id])


@pytest.mark.req("REQ-F-LOG-03")
@pytest.mark.django_db(databases=DBS, transaction=True)
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_event SET outcome = 'failed' WHERE id = %s",
        "DELETE FROM audit_event WHERE id = %s",
    ],
)
def test_maintenance_update_and_delete_hit_the_trigger(event_id: uuid.UUID, statement: str) -> None:
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic(using="maintenance"):
        _rows("maintenance", statement, [event_id])


@pytest.mark.req("REQ-F-LOG-03")
@pytest.mark.django_db(databases=DBS, transaction=True)
def test_truncate_hits_the_trigger(event_id: uuid.UUID) -> None:
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic(using="maintenance"):
        _rows("maintenance", "TRUNCATE audit_event")


@pytest.mark.req("REQ-F-LOG-03")
@pytest.mark.django_db(databases=DBS, transaction=True)
def test_partitions_are_not_reachable_directly_by_the_app_role() -> None:
    partition = _month_names(1)[0]
    with pytest.raises(ProgrammingError, match="permission denied"), transaction.atomic(using="default"):
        _rows("default", f"SELECT count(*) FROM {partition}")


@pytest.mark.req("REQ-F-LOG-03")
@pytest.mark.django_db(databases=DBS, transaction=True)
@pytest.mark.parametrize(
    "values",
    [
        "('robot', 'probe.created', 'success')",
        "('system', 'Probe Created', 'success')",
        "('system', 'probe.created', 'maybe')",
    ],
    ids=["actor_type", "action", "outcome"],
)
def test_check_constraints_reject_unknown_values(values: str) -> None:
    with pytest.raises(DatabaseError, match="check constraint"), transaction.atomic(using="default"):
        _rows(
            "default",
            "INSERT INTO audit_event (id, occurred_at, actor_type, action, outcome) "
            f"SELECT gen_random_uuid(), now(), * FROM (VALUES {values}) v",
        )

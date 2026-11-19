"""AuditLog on PostgreSQL: commits with the change, survives a rollback when rejected (F1.12, ADR-008 §3)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connections

from cherrylove.audit.infrastructure.postgres_audit_log import PostgresAuditLog, RejectedOutsideRollbackError
from cherrylove.shared.application.audit_log import AuditEvent
from cherrylove.shared.application.request_context import current_request_id
from cherrylove.shared.infrastructure.clock import SystemClock, Uuid7Generator
from cherrylove.shared.infrastructure.django_unit_of_work import DjangoUnitOfWork

pytestmark = pytest.mark.integration
DBS = ["default", "maintenance"]


class Rejected(Exception):
    pass


def _rows(sql: str, params: list[Any]) -> list[tuple[Any, ...]]:
    with connections["default"].cursor() as cursor:
        cursor.execute(sql, params)
        return list(cursor.fetchall())


@pytest.fixture
def probe() -> Iterator[str]:
    name = f"audit_probe_{uuid.uuid4().hex[:8]}"
    with connections["maintenance"].cursor() as cursor:
        cursor.execute(f"CREATE TABLE {name} (id uuid PRIMARY KEY)")
    yield name
    with connections["maintenance"].cursor() as cursor:
        cursor.execute(f"DROP TABLE {name}")


def _events(entity_id: uuid.UUID) -> list[tuple[Any, ...]]:
    return _rows(
        "SELECT action, outcome, actor_type, request_id, changes FROM audit_event WHERE entity_id = %s",
        [entity_id],
    )


@pytest.mark.req("REQ-F-LOG-01")
@pytest.mark.django_db(databases=DBS, transaction=True)
def test_in_transaction_write_commits_with_the_change(probe: str) -> None:
    uow, audit, entity = DjangoUnitOfWork(), PostgresAuditLog(SystemClock(), Uuid7Generator()), uuid.uuid7()
    token = current_request_id.set("trace-audit")
    try:
        with uow.atomic():
            _rows(f"INSERT INTO {probe} (id) VALUES (%s) RETURNING id", [entity])
            audit.record(
                AuditEvent(
                    action="probe.created",
                    actor_type="system",
                    entity_type="probe",
                    entity_id=entity,
                    changes={"body": {"changed": True}},
                )
            )
    finally:
        current_request_id.reset(token)
    assert _rows(f"SELECT count(*) FROM {probe} WHERE id = %s", [entity]) == [(1,)]
    assert _events(entity) == [("probe.created", "success", "system", "trace-audit", {"body": {"changed": True}})]


@pytest.mark.req("REQ-F-LOG-01")
@pytest.mark.django_db(databases=DBS, transaction=True)
def test_rollback_removes_the_change_and_its_audit_and_the_rejection_survives(probe: str) -> None:
    uow, audit, entity = DjangoUnitOfWork(), PostgresAuditLog(SystemClock(), Uuid7Generator()), uuid.uuid7()
    event = AuditEvent(action="probe.created", actor_type="system", entity_type="probe", entity_id=entity)
    with pytest.raises(Rejected), uow.atomic():
        _rows(f"INSERT INTO {probe} (id) VALUES (%s) RETURNING id", [entity])
        audit.record(event)
        raise Rejected
    assert _rows(f"SELECT count(*) FROM {probe} WHERE id = %s", [entity]) == [(0,)]
    assert _events(entity) == []

    audit.record_rejected(
        AuditEvent(
            action="probe.created", outcome="rejected", actor_type="system", entity_type="probe", entity_id=entity
        )
    )
    assert [row[:2] for row in _events(entity)] == [("probe.created", "rejected")]


@pytest.mark.req("REQ-F-LOG-01")
@pytest.mark.django_db(databases=DBS, transaction=True)
def test_rejected_write_inside_an_open_transaction_is_refused() -> None:
    audit = PostgresAuditLog(SystemClock(), Uuid7Generator())
    with pytest.raises(RejectedOutsideRollbackError), DjangoUnitOfWork().atomic():
        audit.record_rejected(AuditEvent(action="probe.created", outcome="rejected", actor_type="system"))

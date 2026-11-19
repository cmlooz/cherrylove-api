"""Job queue on django-tasks-db and PostgreSQL (IMPL-API-001 F1.15, ADR-013 §1-2)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django_tasks.exceptions import InvalidTaskError
from django_tasks_db.models import DBTaskResult

from cherrylove.shared.application.job_queue import Payload
from cherrylove.shared.infrastructure.django_job_queue import DjangoJobQueue, register_job, run_job
from cherrylove.shared.infrastructure.django_unit_of_work import DjangoUnitOfWork
from cherrylove.shared.infrastructure.orm import JobExecution

pytestmark = pytest.mark.integration

RUNS: list[Payload] = []


@register_job("test.integration.record")
def record(payload: Payload) -> None:
    RUNS.append(payload)


class Boom(Exception):
    pass


def _key() -> str:
    return f"test:{uuid.uuid4().hex}"


def _rows_for(key: str) -> list[DBTaskResult[Any, Any]]:
    return [row for row in DBTaskResult.objects.all() if row.args_kwargs["args"][2] == key]


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.django_db(transaction=True)
def test_job_row_rolls_back_with_the_transaction() -> None:
    uow, key = DjangoUnitOfWork(), _key()
    with pytest.raises(Boom), uow.atomic():
        DjangoJobQueue().enqueue("test.integration.record", {"n": 1}, idempotency_key=key)
        raise Boom
    assert _rows_for(key) == []

    with uow.atomic():
        DjangoJobQueue().enqueue("test.integration.record", {"n": 1}, idempotency_key=key)
    assert len(_rows_for(key)) == 1


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("queue", ["default", "media"])
def test_default_and_media_queues(queue: str) -> None:
    key = _key()
    DjangoJobQueue().enqueue("test.integration.record", {}, idempotency_key=key, queue=queue)  # type: ignore[arg-type]
    assert [row.queue_name for row in _rows_for(key)] == [queue]


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.django_db(transaction=True)
def test_an_undeclared_queue_is_refused() -> None:
    with pytest.raises(InvalidTaskError):
        DjangoJobQueue().enqueue("test.integration.record", {}, idempotency_key=_key(), queue="bulk")  # type: ignore[arg-type]


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.django_db(transaction=True)
def test_same_idempotency_key_twice_runs_once() -> None:
    key, before = _key(), len(RUNS)
    assert run_job.call("test.integration.record", {"n": 7}, key) is True
    assert run_job.call("test.integration.record", {"n": 7}, key) is False
    assert RUNS[before:] == [{"n": 7}]
    execution = JobExecution.objects.get(idempotency_key=key)
    assert (execution.status, execution.attempts, execution.job) == ("succeeded", 1, "test.integration.record")

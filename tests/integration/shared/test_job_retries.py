"""Job retries on PostgreSQL (IMPL-API-001 F1.17, ADR-013 §2, ADR-008).

Each failed attempt re-enqueues the job with run_after = now + backoff; the 6th failure marks the key failed
and writes a job.failed audit event; after that the key never runs again.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.db import connections
from django_tasks_db.models import DBTaskResult

from cherrylove.shared.application.job_queue import Payload
from cherrylove.shared.infrastructure.clock import SystemClock
from cherrylove.shared.infrastructure.django_job_queue import configure_job_runtime, register_job, run_job
from cherrylove.shared.infrastructure.orm import JobExecution
from tests.fakes.clock import FixedClock

pytestmark = pytest.mark.integration

ATTEMPTS: dict[str, int] = {}


class Flaky(Exception):
    pass


@register_job("test.integration.always_fails")
def always_fails(payload: Payload) -> None:
    raise Flaky


@register_job("test.integration.fails_once")
def fails_once(payload: Payload) -> None:
    key = str(payload["key"])
    ATTEMPTS[key] = ATTEMPTS.get(key, 0) + 1
    if ATTEMPTS[key] == 1:
        raise Flaky


@pytest.fixture
def clock() -> Iterator[FixedClock]:
    fixed = FixedClock()
    configure_job_runtime(clock=fixed)
    yield fixed
    configure_job_runtime(clock=SystemClock())


def _retries(key: str) -> list[DBTaskResult[Any, Any]]:
    rows = [row for row in DBTaskResult.objects.all() if row.args_kwargs["args"][2] == key]
    return sorted(rows, key=lambda row: row.run_after)


def _audit_failures() -> list[dict[str, Any]]:
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT changes FROM audit_event WHERE action = 'job.failed' AND outcome = 'failed'")
        return [json.loads(row[0]) for row in cursor.fetchall()]


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.django_db(transaction=True)
def test_six_failures_back_off_then_fail_and_are_audited(clock: FixedClock) -> None:
    key = f"test:retry:{uuid.uuid4().hex}"
    for attempt in range(1, 6):
        assert run_job.call("test.integration.always_fails", {}, key, "media") is False
        execution = JobExecution.objects.get(idempotency_key=key)
        assert (execution.status, execution.attempts, execution.last_error_code) == ("retrying", attempt, "Flaky")
    retries = _retries(key)
    assert [row.run_after - clock.now() for row in retries] == [timedelta(minutes=m) for m in (1, 4, 16, 64, 240)]
    assert {row.queue_name for row in retries} == {"media"}

    before = len(_audit_failures())
    assert run_job.call("test.integration.always_fails", {}, key, "media") is False
    execution = JobExecution.objects.get(idempotency_key=key)
    assert (execution.status, execution.attempts) == ("failed", 6)
    assert len(_retries(key)) == 5, "no 7th attempt is scheduled"
    failures = _audit_failures()[before:]
    assert {
        "job": {"to": "test.integration.always_fails"},
        "attempts": {"to": 6},
        "last_error_code": {"to": "Flaky"},
    } in failures

    assert run_job.call("test.integration.always_fails", {}, key, "media") is False
    assert JobExecution.objects.get(idempotency_key=key).attempts == 6


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.django_db(transaction=True)
def test_a_retry_that_succeeds_clears_the_error(clock: FixedClock) -> None:
    key = f"test:retry:{uuid.uuid4().hex}"
    assert run_job.call("test.integration.fails_once", {"key": key}, key) is False
    assert run_job.call("test.integration.fails_once", {"key": key}, key) is True
    execution = JobExecution.objects.get(idempotency_key=key)
    assert (execution.status, execution.attempts, execution.last_error_code) == ("succeeded", 2, None)

"""JobQueue port and handler registry without a database (IMPL-API-001 F1.15, ADR-013 §1-2)."""

from __future__ import annotations

import pytest

from cherrylove.shared.application.job_queue import JobQueue, Payload
from cherrylove.shared.infrastructure.django_job_queue import (
    DjangoJobQueue,
    UnknownJobError,
    register_job,
    run_idempotently,
)
from tests.fakes.job_queue import EnqueuedJob, InMemoryJobQueue


def _noop(payload: Payload) -> None:
    return None


@pytest.mark.req("REQ-N-ARC-01")
def test_fake_records_enqueued_jobs() -> None:
    fake = InMemoryJobQueue()
    queue: JobQueue = fake
    queue.enqueue("media.validate", {"media_id": "m1"}, idempotency_key="media:validate:m1", queue="media")
    assert fake.jobs == [EnqueuedJob("media.validate", {"media_id": "m1"}, "media:validate:m1", "media", None)]


@pytest.mark.req("REQ-N-ARC-01")
def test_a_job_name_cannot_be_registered_twice_with_another_handler() -> None:
    register_job("test.unit.noop")(_noop)
    register_job("test.unit.noop")(_noop)  # same handler: idempotent registration
    with pytest.raises(ValueError, match="already registered"):
        register_job("test.unit.noop")(lambda payload: None)


@pytest.mark.req("REQ-N-ARC-01")
def test_unknown_jobs_are_refused_before_touching_the_database() -> None:
    with pytest.raises(UnknownJobError):
        DjangoJobQueue().enqueue("nobody.registered.this", {}, idempotency_key="k")
    with pytest.raises(UnknownJobError):
        run_idempotently("nobody.registered.this", {}, "k")

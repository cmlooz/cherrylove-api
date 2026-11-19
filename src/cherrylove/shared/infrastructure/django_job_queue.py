"""JobQueue on Django Tasks with the database backend (ADR-013 §1-2, ADR-016 §1).

`enqueue()` writes a task row through the current connection, so it commits or rolls back with the use case.
All jobs run through one task, `run_job`, which claims the idempotency key in `shared_job_execution` under a
row lock before calling the registered handler: a key that already succeeded is never run again.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from django.db import transaction
from django_tasks import task

from cherrylove.shared.application.job_queue import Payload, QueueName
from cherrylove.shared.infrastructure.orm import JobExecution

type JobHandler = Callable[[Payload], None]

_HANDLERS: dict[str, JobHandler] = {}


class UnknownJobError(LookupError):
    pass


def register_job(name: str) -> Callable[[JobHandler], JobHandler]:
    """Modules register their handlers from `interfaces/jobs.py`."""

    def decorator(handler: JobHandler) -> JobHandler:
        if name in _HANDLERS and _HANDLERS[name] is not handler:
            raise ValueError(f"job {name!r} is already registered")
        _HANDLERS[name] = handler
        return handler

    return decorator


def run_idempotently(job: str, payload: Payload, idempotency_key: str) -> bool:
    """Run the handler once per key; False when the key already succeeded (ADR-013 §2)."""
    handler = _HANDLERS.get(job)
    if handler is None:
        raise UnknownJobError(job)
    with transaction.atomic():
        execution, _ = JobExecution.objects.select_for_update().get_or_create(
            idempotency_key=idempotency_key,
            defaults={"job": job, "status": JobExecution.Status.RUNNING},
        )
        if execution.status == JobExecution.Status.SUCCEEDED:
            return False
        execution.attempts += 1
        execution.status = JobExecution.Status.RUNNING
        execution.save(update_fields=["attempts", "status", "updated_at"])
        handler(payload)
        execution.status = JobExecution.Status.SUCCEEDED
        execution.save(update_fields=["status", "updated_at"])
    return True


@task()
def run_job(job: str, payload: dict[str, object], idempotency_key: str) -> bool:
    return run_idempotently(job, payload, idempotency_key)  # type: ignore[arg-type]


class DjangoJobQueue:
    def enqueue(
        self,
        job: str,
        payload: Payload,
        *,
        idempotency_key: str,
        queue: QueueName = "default",
        run_after: datetime | None = None,
    ) -> None:
        if job not in _HANDLERS:
            raise UnknownJobError(job)
        configured = run_job.using(queue_name=queue, run_after=run_after)
        configured.enqueue(job, dict(payload), idempotency_key)

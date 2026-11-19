"""JobQueue on Django Tasks with the database backend (ADR-013 §1-2, ADR-016 §1).

`enqueue()` writes a task row through the current connection, so it commits or rolls back with the use case.
All jobs run through one task, `run_job`, which claims the idempotency key in `shared_job_execution` under a
row lock before calling the registered handler: a key that already succeeded is never run again.

A failing handler is retried with backoff (1 min → 4 h, at most 6 attempts, F1.17): its savepoint is rolled
back, the attempt is recorded and the same job is re-enqueued with `run_after`. The 6th failure marks the key
`failed` and writes a `job.failed` audit event in the same transaction. This runner is an adapter boundary,
so catching the handler's exception here is allowed (ADR-010 §3).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django_tasks import task

from cherrylove.shared.application.audit_log import AuditEvent, AuditLog
from cherrylove.shared.application.job_queue import Payload, QueueName
from cherrylove.shared.application.retry_policy import delay_after
from cherrylove.shared.domain.clock import Clock
from cherrylove.shared.infrastructure.clock import SystemClock
from cherrylove.shared.infrastructure.orm import JobExecution

logger = logging.getLogger("cherrylove.jobs")

type JobHandler = Callable[[Payload], None]

_HANDLERS: dict[str, JobHandler] = {}


class UnknownJobError(LookupError):
    pass


class JobRuntimeNotConfiguredError(RuntimeError):
    """No AuditLog was injected, so a terminal failure could not be audited (ADR-013 §2)."""


@dataclass
class JobRuntime:
    clock: Clock
    audit: AuditLog | None = None


_runtime = JobRuntime(clock=SystemClock())


def configure_job_runtime(*, clock: Clock | None = None, audit: AuditLog | None = None) -> None:
    """Composition root hook: the audit app injects its adapter at startup (the kernel cannot import it)."""
    if clock is not None:
        _runtime.clock = clock
    if audit is not None:
        _runtime.audit = audit


def register_job(name: str) -> Callable[[JobHandler], JobHandler]:
    """Modules register their handlers from `interfaces/jobs.py`."""

    def decorator(handler: JobHandler) -> JobHandler:
        if name in _HANDLERS and _HANDLERS[name] is not handler:
            raise ValueError(f"job {name!r} is already registered")
        _HANDLERS[name] = handler
        return handler

    return decorator


def run_idempotently(job: str, payload: Payload, idempotency_key: str, queue: QueueName = "default") -> bool:
    """Run the handler once per key; True only when this call ran it successfully (ADR-013 §2)."""
    handler = _HANDLERS.get(job)
    if handler is None:
        raise UnknownJobError(job)
    with transaction.atomic():
        execution, _ = JobExecution.objects.select_for_update().get_or_create(
            idempotency_key=idempotency_key,
            defaults={"job": job, "status": JobExecution.Status.RUNNING},
        )
        if execution.status in {JobExecution.Status.SUCCEEDED, JobExecution.Status.FAILED}:
            return False
        execution.attempts += 1
        try:
            with transaction.atomic():
                handler(payload)
        except Exception as error:
            _handle_failure(execution, job, payload, queue, error)
            return False
        execution.status = JobExecution.Status.SUCCEEDED
        execution.last_error_code = None
        execution.save()
    return True


def _handle_failure(execution: JobExecution, job: str, payload: Payload, queue: QueueName, error: Exception) -> None:
    execution.last_error_code = type(error).__name__[:100]
    delay = delay_after(execution.attempts)
    if delay is None:
        execution.status = JobExecution.Status.FAILED
        _audit_terminal_failure(execution)
        logger.error("job failed for good", extra={"job": job, "attempts": execution.attempts})
    else:
        execution.status = JobExecution.Status.RETRYING
        run_after = _runtime.clock.now() + delay
        run_job.using(queue_name=queue, run_after=run_after).enqueue(
            job, dict(payload), execution.idempotency_key, queue
        )
        logger.warning("job failed, retrying", extra={"job": job, "attempt": execution.attempts})
    execution.save()


def _audit_terminal_failure(execution: JobExecution) -> None:
    if _runtime.audit is None:
        raise JobRuntimeNotConfiguredError("configure_job_runtime(audit=...) was never called")
    _runtime.audit.record(
        AuditEvent(
            action="job.failed",
            outcome="failed",
            actor_type="system",
            entity_type="job",
            changes={
                "job": {"to": execution.job},
                "attempts": {"to": execution.attempts},
                "last_error_code": {"to": execution.last_error_code},
            },
        )
    )


@task()
def run_job(job: str, payload: dict[str, object], idempotency_key: str, queue: str = "default") -> bool:
    return run_idempotently(job, payload, idempotency_key, queue)  # type: ignore[arg-type]


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
        configured.enqueue(job, dict(payload), idempotency_key, queue)

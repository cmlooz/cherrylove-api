"""In-memory JobQueue: records what a use case enqueued (ADR-013 §1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from cherrylove.shared.application.job_queue import Payload, QueueName


@dataclass(frozen=True)
class EnqueuedJob:
    job: str
    payload: Payload
    idempotency_key: str
    queue: QueueName
    run_after: datetime | None


@dataclass
class InMemoryJobQueue:
    jobs: list[EnqueuedJob] = field(default_factory=list)

    def enqueue(
        self,
        job: str,
        payload: Payload,
        *,
        idempotency_key: str,
        queue: QueueName = "default",
        run_after: datetime | None = None,
    ) -> None:
        self.jobs.append(EnqueuedJob(job, dict(payload), idempotency_key, queue, run_after))

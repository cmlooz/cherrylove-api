"""JobQueue port (ADR-013 §1-2).

Reliable side effects are enqueued **inside** the use-case transaction: the job exists only if the change
committed. Every job carries an idempotency key; a second run with the same key is a no-op. Two queues keep
slow media work away from pushes and emails.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Literal, Protocol

from cherrylove.shared.application.cache import Cacheable

type QueueName = Literal["default", "media"]
type Payload = Mapping[str, Cacheable]


class JobQueue(Protocol):
    def enqueue(
        self,
        job: str,
        payload: Payload,
        *,
        idempotency_key: str,
        queue: QueueName = "default",
        run_after: datetime | None = None,
    ) -> None:
        """`job` is a registered handler name, e.g. `identity.send_invite_email`."""
        ...

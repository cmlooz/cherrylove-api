"""PostgreSQL adapter of the AuditLog port (ADR-008 §3): raw inserts into the partitioned audit_event."""

from __future__ import annotations

import json

from django.db import connections

from cherrylove.shared.application.audit_log import AuditEvent
from cherrylove.shared.application.request_context import current_request_id
from cherrylove.shared.domain.clock import Clock
from cherrylove.shared.domain.ids import IdGenerator

INSERT = """
INSERT INTO audit_event (id, occurred_at, request_id, actor_type, actor_id, couple_id, action, outcome,
                         entity_type, entity_id, ip, device, changes)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
"""


class RejectedOutsideRollbackError(RuntimeError):
    """record_rejected() ran inside an open transaction, where a rollback would erase it."""


class PostgresAuditLog:
    def __init__(self, clock: Clock, ids: IdGenerator, using: str = "default") -> None:
        self._clock = clock
        self._ids = ids
        self._using = using

    def record(self, event: AuditEvent) -> None:
        self._insert(event)

    def record_rejected(self, event: AuditEvent) -> None:
        if connections[self._using].in_atomic_block:
            raise RejectedOutsideRollbackError("call record_rejected() after the unit of work has rolled back")
        self._insert(event)

    def _insert(self, event: AuditEvent) -> None:
        actor = event.actor
        with connections[self._using].cursor() as cursor:
            cursor.execute(
                INSERT,
                [
                    self._ids.new(),
                    self._clock.now(),
                    current_request_id.get(),
                    event.resolved_actor_type,
                    actor.user_id.value if actor else None,
                    actor.couple_id.value if actor else None,
                    event.action,
                    event.outcome,
                    event.entity_type,
                    event.entity_id,
                    event.ip,
                    json.dumps(dict(event.device)),
                    json.dumps(dict(event.changes)),
                ],
            )

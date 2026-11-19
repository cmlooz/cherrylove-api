"""In-memory AuditLog: separates in-transaction events from rejected attempts (ADR-008 §3)."""

from __future__ import annotations

from dataclasses import dataclass, field

from cherrylove.shared.application.audit_log import AuditEvent


@dataclass
class InMemoryAuditLog:
    events: list[AuditEvent] = field(default_factory=list)
    rejected: list[AuditEvent] = field(default_factory=list)

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)

    def record_rejected(self, event: AuditEvent) -> None:
        self.rejected.append(event)

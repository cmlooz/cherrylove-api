from __future__ import annotations

from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = "cherrylove.audit"
    label = "audit"

    def ready(self) -> None:
        # Composition root: other modules get the AuditLog port through audit.application.public, and the
        # shared job runner audits terminal failures through it (ADR-001 §3, ADR-013 §2).
        from cherrylove.audit.application.public import register_audit_log  # noqa: PLC0415
        from cherrylove.audit.infrastructure.postgres_audit_log import PostgresAuditLog  # noqa: PLC0415
        from cherrylove.shared.infrastructure.clock import SystemClock, Uuid7Generator  # noqa: PLC0415
        from cherrylove.shared.infrastructure.django_job_queue import configure_job_runtime  # noqa: PLC0415

        audit_log = PostgresAuditLog(SystemClock(), Uuid7Generator())
        register_audit_log(audit_log)
        configure_job_runtime(audit=audit_log)

from __future__ import annotations

from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = "cherrylove.audit"
    label = "audit"

    def ready(self) -> None:
        # Composition root: the shared job runner audits terminal failures through this module (ADR-013 §2).
        from cherrylove.audit.infrastructure.postgres_audit_log import PostgresAuditLog  # noqa: PLC0415
        from cherrylove.shared.infrastructure.clock import SystemClock, Uuid7Generator  # noqa: PLC0415
        from cherrylove.shared.infrastructure.django_job_queue import configure_job_runtime  # noqa: PLC0415

        configure_job_runtime(audit=PostgresAuditLog(SystemClock(), Uuid7Generator()))

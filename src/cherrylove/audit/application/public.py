"""Audit facade for other modules (ADR-001 §3): hands out the AuditLog port, never the adapter class."""

from __future__ import annotations

from cherrylove.shared.application.audit_log import AuditLog

_audit_log: AuditLog | None = None


def register_audit_log(audit_log: AuditLog) -> None:
    global _audit_log  # noqa: PLW0603 - composition-root hook, set once at startup
    _audit_log = audit_log


def audit_log() -> AuditLog:
    if _audit_log is None:
        raise RuntimeError("the audit app is not ready: no AuditLog registered")
    return _audit_log

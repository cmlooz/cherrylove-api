"""The request being served, as context for logs and adapters (REQ-N-QA-01).

Set by the HTTP middleware (interfaces) and read by the log filter (infrastructure); it lives here so both
layers depend inward on it (ADR-001 §2).
"""

from __future__ import annotations

from contextvars import ContextVar

current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)

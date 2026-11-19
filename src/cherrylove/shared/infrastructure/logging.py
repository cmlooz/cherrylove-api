"""Operational JSON logs to stdout with the request ID (ADR-008 §7, REQ-N-QA-01).

Not the audit trail: not append-only, and never content. The ID of the request being served lives in a
context variable, so every log line written while serving it carries the same `request_id`.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from cherrylove.shared.application.request_context import current_request_id

_STANDARD = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "request_id"}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = current_request_id.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        line.update({key: value for key, value in vars(record).items() if key not in _STANDARD})
        if record.exc_info:
            line["exc"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str, ensure_ascii=False)

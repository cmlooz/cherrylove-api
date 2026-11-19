"""`X-Request-ID` end to end: client → API → logs → problem bodies (REQ-N-QA-01, ADR-008 §7).

A client-sent ID is kept only if it is at most 64 characters of a safe charset (it ends up in logs and
headers); otherwise the server generates one. The ID is echoed on every response.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from cherrylove.shared.application.request_context import current_request_id

HEADER = "X-Request-ID"
SAFE_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


def accepted_request_id(raw: str | None) -> str:
    if raw is not None and SAFE_ID.fullmatch(raw):
        return raw
    return uuid.uuid4().hex


class RequestIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = accepted_request_id(request.headers.get(HEADER))
        request.request_id = request_id  # type: ignore[attr-defined]
        token = current_request_id.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            current_request_id.reset(token)
        response[HEADER] = request_id
        return response

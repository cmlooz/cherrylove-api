"""RFC 9457 problem details: the one place where exceptions become responses (ADR-010, REQ-N-QA-02).

DRF calls `exception_handler` for every exception raised in an API view; Django calls `not_found_view` and
`server_error_view` for everything else. Clients branch on `code` (contract `ErrorCode`) and, for validation,
on `errors[].code` (contract `FieldErrorCode`, DEC-046). Internals never leak: a 500 carries only `code`,
`title`, `status` and `request_id`; the stack trace goes to the log with the same `request_id`.
"""

from __future__ import annotations

import logging
import math
import uuid
from collections.abc import Iterator, Mapping
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from rest_framework import exceptions as drf
from rest_framework.response import Response

from cherrylove.shared.domain.errors import DomainError, FieldError

logger = logging.getLogger("cherrylove.problems")

CONTENT_TYPE = "application/problem+json"

# DRF field error codes → contract FieldErrorCode (DEC-046). Anything unknown becomes invalid_format.
FIELD_CODES: Mapping[str, str] = {
    "required": "required",
    "null": "null_not_allowed",
    "blank": "too_short",
    "min_length": "too_short",
    "max_length": "too_long",
    "min_value": "below_minimum",
    "max_value": "above_maximum",
    "invalid_choice": "invalid_choice",
    "empty": "too_few_items",
    "not_a_list": "invalid_type",
    "not_a_dict": "invalid_type",
    "invalid": "invalid_format",
    "max_digits": "too_long",
    "max_decimal_places": "too_long",
}

TITLES: Mapping[str, str] = {
    "validation_failed": "Invalid input",
    "not_authenticated": "Not authenticated",
    "not_found": "Not found",
    "rate_limited": "Too many requests",
    "internal_error": "Internal error",
}


def _pointer(path: tuple[str | int, ...]) -> str:
    """RFC 6901 JSON Pointer: `~` → `~0`, `/` → `~1`; DRF non-field errors point at the document root."""
    tokens = [str(part).replace("~", "~0").replace("/", "~1") for part in path if part != "non_field_errors"]
    return "".join(f"/{token}" for token in tokens)


def _field_errors(detail: Any, path: tuple[str | int, ...] = ()) -> Iterator[dict[str, object]]:
    if isinstance(detail, Mapping):
        for key, value in detail.items():
            yield from _field_errors(value, (*path, key))
    elif isinstance(detail, list):
        if all(isinstance(item, drf.ErrorDetail) for item in detail):
            for item in detail:
                yield {"pointer": _pointer(path), "code": FIELD_CODES.get(item.code or "", "invalid_format")}
        else:
            for index, item in enumerate(detail):
                yield from _field_errors(item, (*path, index))
    elif isinstance(detail, drf.ErrorDetail):
        yield {"pointer": _pointer(path), "code": FIELD_CODES.get(detail.code or "", "invalid_format")}


def request_id_of(request: HttpRequest | None) -> str:
    value = getattr(request, "request_id", None) if request is not None else None
    return value if isinstance(value, str) and value else uuid.uuid4().hex


def problem(  # noqa: PLR0913 - one named argument per optional RFC 9457 member
    code: str,
    status: int,
    request: HttpRequest | None,
    *,
    detail: str = "",
    params: Mapping[str, object] | None = None,
    errors: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "type": f"/problems/{code.replace('_', '-')}",
        "title": TITLES.get(code, code.replace("_", " ").capitalize()),
        "status": status,
        "code": code,
        "request_id": request_id_of(request),
    }
    if request is not None:
        body["instance"] = request.path
    if detail:
        body["detail"] = detail
    if params:
        body["params"] = dict(params)
    if errors is not None:
        body["errors"] = errors
    return body


def to_problem(exc: BaseException, request: HttpRequest | None) -> tuple[dict[str, object], dict[str, str]]:
    """(body, extra headers) for any exception."""
    headers: dict[str, str] = {}
    if isinstance(exc, FieldError):
        error: dict[str, object] = {"pointer": exc.pointer, "code": exc.field_code}
        if exc.params:
            error["params"] = dict(exc.params)
        body = problem(exc.code, exc.status, request, errors=[error])
    elif isinstance(exc, DomainError):
        body = problem(exc.code, exc.status, request, detail=exc.detail, params=exc.params)
    elif isinstance(exc, drf.ValidationError):
        body = problem("validation_failed", 400, request, errors=list(_field_errors(exc.detail)))
    elif isinstance(exc, drf.ParseError | drf.UnsupportedMediaType):
        body = problem("validation_failed", 400, request, errors=[{"pointer": "", "code": "invalid_format"}])
    elif isinstance(exc, drf.NotAuthenticated | drf.AuthenticationFailed):
        body = problem("not_authenticated", 401, request)
    elif isinstance(exc, drf.Throttled):
        wait = max(1, math.ceil(getattr(exc, "wait", None) or 1))
        body = problem("rate_limited", 429, request, params={"retry_after": wait})
        headers["Retry-After"] = str(wait)
    elif isinstance(exc, Http404 | drf.NotFound):
        body = problem("not_found", 404, request)
    else:
        body = problem("internal_error", 500, request)
        logger.error("unhandled exception", exc_info=exc, extra={"request_id": body["request_id"]})
    return body, headers


def exception_handler(exc: Exception, context: Mapping[str, Any]) -> Response:
    """DRF `EXCEPTION_HANDLER`: every exception raised in an API view ends here."""
    request = context.get("request")
    django_request: HttpRequest | None = getattr(request, "_request", request)
    body, headers = to_problem(exc, django_request)
    return Response(body, status=int(str(body["status"])), headers=headers, content_type=CONTENT_TYPE)


def _json(body: dict[str, object]) -> HttpResponse:
    return JsonResponse(body, status=int(str(body["status"])), content_type=CONTENT_TYPE)


def not_found_view(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    """Django `handler404`: unknown URLs answer with the same problem shape."""
    return _json(problem("not_found", 404, request))


def server_error_view(request: HttpRequest) -> HttpResponse:
    """Django `handler500`: generic body; Django already logged the exception."""
    return _json(problem("internal_error", 500, request))

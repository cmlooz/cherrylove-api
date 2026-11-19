"""Request ID end to end and JSON logs (IMPL-API-001 F1.8, REQ-N-QA-01, ADR-008 §7)."""

from __future__ import annotations

import json
import logging
import sys

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory

from cherrylove.shared.application.request_context import current_request_id
from cherrylove.shared.infrastructure.logging import JsonFormatter, RequestIdFilter
from cherrylove.shared.interfaces.http.middleware.request_id import RequestIdMiddleware, accepted_request_id

log = logging.getLogger("cherrylove.test.request_id")


@pytest.mark.req("REQ-N-QA-01")
@pytest.mark.parametrize("raw", ["abc", "9f1c2b7e-4a5d.4c3b_X", "a" * 64])
def test_safe_client_ids_are_kept(raw: str) -> None:
    assert accepted_request_id(raw) == raw


@pytest.mark.req("REQ-N-QA-01")
@pytest.mark.parametrize("raw", [None, "", "a" * 65, "has space", "line\nbreak", "<script>", "ñandú"])
def test_unsafe_or_missing_ids_are_replaced(raw: str | None) -> None:
    generated = accepted_request_id(raw)
    assert generated != raw
    assert len(generated) == 32


@pytest.mark.req("REQ-N-QA-01")
def test_id_is_echoed_and_visible_to_the_view_and_logs() -> None:
    seen: dict[str, object] = {}

    def view(request: HttpRequest) -> HttpResponse:
        seen["request"] = getattr(request, "request_id", None)
        seen["context"] = current_request_id.get()
        return HttpResponse("ok")

    response = RequestIdMiddleware(view)(RequestFactory().get("/", headers={"X-Request-ID": "client-42"}))
    assert response["X-Request-ID"] == "client-42"
    assert seen == {"request": "client-42", "context": "client-42"}
    assert current_request_id.get() is None, "the ID must not leak into the next request"


@pytest.mark.req("REQ-N-QA-01")
def test_generated_id_is_echoed() -> None:
    response = RequestIdMiddleware(lambda request: HttpResponse())(RequestFactory().get("/"))
    assert len(response["X-Request-ID"]) == 32


@pytest.mark.req("REQ-N-QA-01")
def test_problem_bodies_carry_the_same_id(client: Client) -> None:
    response = client.get("/no/such/path", headers={"X-Request-ID": "trace-7"})
    assert response["X-Request-ID"] == "trace-7"
    assert response.json()["request_id"] == "trace-7"


def _format(record: logging.LogRecord) -> dict[str, object]:
    RequestIdFilter().filter(record)
    parsed: dict[str, object] = json.loads(JsonFormatter().format(record))
    return parsed


@pytest.mark.req("REQ-N-QA-01")
def test_log_lines_are_json_with_the_current_request_id() -> None:
    token = current_request_id.set("trace-9")
    try:
        record = log.makeRecord(log.name, logging.INFO, __file__, 1, "card %s published", ("c1",), None)
        line = _format(record)
    finally:
        current_request_id.reset(token)
    assert line["request_id"] == "trace-9"
    assert line["message"] == "card c1 published"
    assert line["level"] == "INFO"
    assert line["logger"] == log.name
    assert str(line["ts"]).endswith("+00:00")


@pytest.mark.req("REQ-N-QA-01")
def test_explicit_request_id_extra_and_exceptions_are_kept() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()
    record = log.makeRecord(
        log.name, logging.ERROR, __file__, 1, "failed", (), exc_info, extra={"request_id": "r-1", "job": "publish"}
    )
    line = _format(record)
    assert line["request_id"] == "r-1"
    assert line["job"] == "publish"
    assert "ValueError: boom" in str(line["exc"])


@pytest.mark.req("REQ-N-QA-01")
def test_outside_a_request_the_id_is_null() -> None:
    line = _format(log.makeRecord(log.name, logging.INFO, __file__, 1, "tick", (), None))
    assert line["request_id"] is None

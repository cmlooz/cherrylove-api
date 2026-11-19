"""RFC 9457 problem details handler (IMPL-API-001 F1.7, ADR-010, REQ-N-QA-02)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
import yaml
from django.http import Http404
from django.test import Client
from rest_framework import exceptions as drf
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from cherrylove.shared.domain.errors import DomainError, FieldError, NotAuthor, NotFound
from cherrylove.shared.interfaces.http.problem_details import FIELD_CODES, exception_handler

CONTRACT = yaml.safe_load((Path(__file__).resolve().parents[3] / "contract" / "openapi.v1.yaml").read_text("utf-8"))
SCHEMAS = CONTRACT["components"]["schemas"]
ERROR_CODES = set(SCHEMAS["ErrorCode"]["enum"])
FIELD_ERROR_CODES = set(SCHEMAS["FieldErrorCode"]["enum"])
REQUIRED = set(SCHEMAS["Problem"]["required"])


class QuotaExceeded(DomainError):
    code = "quota_exceeded"
    status = 409


class NoteSerializer(serializers.Serializer[Any]):
    body = serializers.CharField(max_length=5)
    visibility = serializers.ChoiceField(choices=["shared", "only_me"])
    tags = serializers.ListField(child=serializers.CharField(max_length=3), required=False)
    meta = serializers.DictField(child=serializers.IntegerField(max_value=9), required=False)


class Raising(APIView):
    authentication_classes = ()
    permission_classes = ()
    to_raise: BaseException = RuntimeError("boom")

    def post(self, request: Request) -> Response:
        raise self.to_raise


def _call(exc: BaseException, *, path: str = "/api/v1/cards/x", request_id: str = "req-1") -> Response:
    request = APIRequestFactory().post(path, {}, format="json")
    request.request_id = request_id  # type: ignore[attr-defined]
    view = Raising.as_view(to_raise=exc)
    response: Response = view(request)
    response.render()
    return response


def _assert_problem(response: Response, status: int, code: str) -> dict[str, Any]:
    body: dict[str, Any] = response.data
    assert response.status_code == status
    assert response["Content-Type"].startswith("application/problem+json")
    assert set(body) >= REQUIRED
    assert body["code"] == code
    assert body["code"] in ERROR_CODES
    assert body["status"] == status
    assert body["type"] == f"/problems/{code.replace('_', '-')}"
    assert body["request_id"] == "req-1"
    return body


@pytest.mark.req("REQ-N-QA-02")
@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (NotFound(), 404, "not_found"),
        (NotAuthor("only the author"), 403, "not_author"),
        (QuotaExceeded(limit_bytes=5), 409, "quota_exceeded"),
        (Http404(), 404, "not_found"),
        (drf.NotFound(), 404, "not_found"),
        (drf.NotAuthenticated(), 401, "not_authenticated"),
        (drf.AuthenticationFailed(), 401, "not_authenticated"),
        (drf.ParseError(), 400, "validation_failed"),
    ],
)
def test_known_exceptions_map_to_their_contract_code(exc: BaseException, status: int, code: str) -> None:
    body = _assert_problem(_call(exc), status, code)
    assert body["instance"] == "/api/v1/cards/x"


@pytest.mark.req("REQ-N-QA-02")
def test_domain_params_travel_but_never_content() -> None:
    body = _assert_problem(_call(QuotaExceeded("over", limit_bytes=5)), 409, "quota_exceeded")
    assert body["params"] == {"limit_bytes": 5}
    assert body["detail"] == "over"


@pytest.mark.req("REQ-N-QA-02")
def test_field_error_becomes_one_pointer() -> None:
    body = _assert_problem(_call(FieldError("/id", "invalid_uuid_version")), 400, "validation_failed")
    assert body["errors"] == [{"pointer": "/id", "code": "invalid_uuid_version"}]


@pytest.mark.req("REQ-N-QA-02")
def test_drf_validation_errors_become_json_pointers_with_field_error_codes() -> None:
    serializer = NoteSerializer(
        data={"body": "too long", "visibility": "public", "tags": ["ok", "toolong"], "meta": {"a/b~c": 99}}
    )
    assert not serializer.is_valid()
    body = _assert_problem(_call(drf.ValidationError(serializer.errors)), 400, "validation_failed")
    assert sorted(body["errors"], key=lambda e: e["pointer"]) == [
        {"pointer": "/body", "code": "too_long"},
        {"pointer": "/meta/a~1b~0c", "code": "above_maximum"},
        {"pointer": "/tags/1", "code": "too_long"},
        {"pointer": "/visibility", "code": "invalid_choice"},
    ]
    assert {error["code"] for error in body["errors"]} <= FIELD_ERROR_CODES


@pytest.mark.req("REQ-N-QA-02")
def test_missing_fields_and_non_field_errors() -> None:
    serializer = NoteSerializer(data={})
    assert not serializer.is_valid()
    body = _assert_problem(_call(drf.ValidationError(serializer.errors)), 400, "validation_failed")
    assert {"pointer": "/body", "code": "required"} in body["errors"]
    root = _call(drf.ValidationError({"non_field_errors": [drf.ErrorDetail("x", code="unique")]})).data
    assert root["errors"] == [{"pointer": "", "code": "invalid_format"}]
    single = _call(drf.ValidationError(drf.ErrorDetail("x", code="required"))).data
    assert single["errors"] == [{"pointer": "", "code": "required"}]


@pytest.mark.req("REQ-N-QA-02")
def test_every_mapped_field_code_is_in_the_contract() -> None:
    assert set(FIELD_CODES.values()) <= FIELD_ERROR_CODES
    assert "invalid_format" in FIELD_ERROR_CODES


@pytest.mark.req("REQ-N-QA-02")
@pytest.mark.parametrize(("wait", "retry_after"), [(None, "1"), (0.2, "1"), (41.3, "42")])
def test_throttled_sets_retry_after(wait: float | None, retry_after: str) -> None:
    response = _call(drf.Throttled(wait=wait))
    body = _assert_problem(response, 429, "rate_limited")
    assert response["Retry-After"] == retry_after
    assert body["params"] == {"retry_after": int(retry_after)}


@pytest.mark.req("REQ-N-QA-02")
def test_unknown_exception_is_a_generic_500_logged_with_its_request_id(caplog: pytest.LogCaptureFixture) -> None:
    leak = "SELECT * FROM identity_user WHERE password = 'hunter2'"
    with caplog.at_level(logging.ERROR, logger="cherrylove.problems"):
        response = _call(RuntimeError(leak))
    body = _assert_problem(response, 500, "internal_error")
    assert set(body) == {"type", "title", "status", "code", "request_id", "instance"}
    assert leak not in str(body)
    assert caplog.records[0].exc_info is not None
    assert caplog.records[0].request_id == "req-1"  # type: ignore[attr-defined]


@pytest.mark.req("REQ-N-QA-02")
def test_request_id_is_always_present() -> None:
    body = exception_handler(NotFound(), {"request": None}).data
    assert len(body["request_id"]) == 32
    assert "instance" not in body


@pytest.mark.req("REQ-N-QA-02")
def test_unknown_urls_answer_with_a_problem(client: Client) -> None:
    response = client.get("/no/such/path")
    assert response.status_code == 404
    assert response["Content-Type"] == "application/problem+json"
    assert response.json()["code"] == "not_found"

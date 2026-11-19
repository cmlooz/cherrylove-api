"""Opaque cursor pagination (IMPL-API-001 F1.10, REQ-N-PERF-02, ADR-003 §5)."""

from __future__ import annotations

import base64

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cherrylove.shared.application.pagination import Page
from cherrylove.shared.domain.errors import FieldError
from cherrylove.shared.interfaces.http.pagination import (
    decode_cursor,
    encode_cursor,
    page_body,
    parse_limit,
    parse_page_request,
)

SCOPE = "0193a5b2-7c3e-7d4a-9f00-1b2c3d4e5f60:cards_list_mine"
positions = st.dictionaries(
    st.text(min_size=1, max_size=12), st.one_of(st.integers(), st.text(max_size=40)), min_size=1, max_size=4
)


@pytest.mark.req("REQ-N-PERF-02")
@given(position=positions)
def test_cursor_round_trip(position: dict[str, str | int]) -> None:
    cursor = encode_cursor(position, SCOPE)
    assert decode_cursor(cursor, SCOPE) == position


@pytest.mark.req("REQ-N-PERF-02")
def test_cursor_is_opaque() -> None:
    cursor = encode_cursor({"memory_date": "2026-10-31", "id": "0193a5b2"}, SCOPE)
    assert "memory_date" not in cursor
    assert "2026-10-31" not in cursor


def _field_code(cursor: str, scope: str = SCOPE) -> str:
    with pytest.raises(FieldError) as error:
        decode_cursor(cursor, scope)
    assert error.value.pointer == "/cursor"
    return error.value.field_code


@pytest.mark.req("REQ-N-PERF-02")
def test_tampered_cursor_is_rejected() -> None:
    cursor = encode_cursor({"id": 10}, SCOPE)
    payload, signature = cursor.rsplit(":", 1)
    assert _field_code(f"{payload}:{signature[::-1]}") == "invalid_cursor"
    forged = base64.urlsafe_b64encode(b'{"id":999}').decode().rstrip("=")
    assert _field_code(f"{forged}:{signature}") == "invalid_cursor"
    assert _field_code("garbage") == "invalid_cursor"


@pytest.mark.req("REQ-N-PERF-02")
def test_cursor_of_another_couple_or_endpoint_is_rejected() -> None:
    cursor = encode_cursor({"id": 10}, SCOPE)
    assert _field_code(cursor, "0193a5b2-8d4f-7e5b-a011-2c3d4e5f6071:cards_list_mine") == "invalid_cursor"
    assert _field_code(cursor, "0193a5b2-7c3e-7d4a-9f00-1b2c3d4e5f60:memories_list_memories") == "invalid_cursor"


@pytest.mark.req("REQ-N-PERF-02")
def test_signed_but_wrong_shape_is_rejected() -> None:
    from django.core import signing  # noqa: PLC0415 - only this test forges a signed non-dict payload

    assert _field_code(signing.dumps([1, 2], salt=f"cherrylove.cursor:{SCOPE}")) == "invalid_cursor"
    assert _field_code(signing.dumps({"id": [1]}, salt=f"cherrylove.cursor:{SCOPE}")) == "invalid_cursor"


@pytest.mark.req("REQ-N-PERF-02")
@pytest.mark.parametrize(("raw", "limit"), [(None, 50), ("", 50), ("1", 1), ("50", 50), ("500", 500)])
def test_limit_defaults_to_50_and_accepts_1_to_500(raw: str | None, limit: int) -> None:
    assert parse_limit(raw) == limit


@pytest.mark.req("REQ-N-PERF-02")
@pytest.mark.parametrize(
    ("raw", "code"),
    [("0", "below_minimum"), ("501", "above_maximum"), ("-1", "invalid_type"), ("ten", "invalid_type")],
)
def test_limit_out_of_range_is_a_field_error(raw: str, code: str) -> None:
    with pytest.raises(FieldError) as error:
        parse_limit(raw)
    assert (error.value.pointer, error.value.field_code) == ("/limit", code)


@pytest.mark.req("REQ-N-PERF-02")
def test_first_page_then_next_page() -> None:
    first = parse_page_request({}, SCOPE)
    assert (first.position, first.limit) == (None, 50)
    body = page_body(Page(results=[1, 2], next_position={"id": 2}), SCOPE, lambda item: {"n": item})
    assert body["results"] == [{"n": 1}, {"n": 2}]
    assert isinstance(body["next_cursor"], str)
    following = parse_page_request({"cursor": body["next_cursor"], "limit": "2"}, SCOPE)
    assert (following.position, following.limit) == ({"id": 2}, 2)


@pytest.mark.req("REQ-N-PERF-02")
def test_last_page_has_a_null_cursor() -> None:
    assert page_body(Page(results=[], next_position=None), SCOPE, str) == {"results": [], "next_cursor": None}

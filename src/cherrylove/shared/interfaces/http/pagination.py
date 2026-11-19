"""Opaque, tamper-proof cursors and the `limit` parameter (REQ-N-PERF-02, ADR-003 §5).

A cursor is the keyset position signed with HMAC (`django.core.signing`, keyed by SECRET_KEY) under a
*scope* such as `"{couple_id}:cards_list_mine"`: a cursor edited by hand, or taken from another couple or
another endpoint, fails with `400 validation_failed` and field code `invalid_cursor` (FieldErrorCode).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from django.core import signing

from cherrylove.shared.application.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page, PageRequest, Position
from cherrylove.shared.domain.errors import FieldError

SALT = "cherrylove.cursor"


def encode_cursor(position: Position, scope: str) -> str:
    return signing.dumps(dict(position), salt=f"{SALT}:{scope}", compress=True)


def decode_cursor(cursor: str, scope: str) -> Position:
    try:
        value = signing.loads(cursor, salt=f"{SALT}:{scope}")
    except signing.BadSignature:
        raise FieldError("/cursor", "invalid_cursor") from None
    if not isinstance(value, dict) or not all(isinstance(v, str | int) for v in value.values()):
        raise FieldError("/cursor", "invalid_cursor")
    return value


def parse_limit(raw: str | None) -> int:
    if raw is None or raw == "":
        return DEFAULT_LIMIT
    if not raw.isdigit():
        raise FieldError("/limit", "invalid_type")
    limit = int(raw)
    if limit < 1:
        raise FieldError("/limit", "below_minimum", min=1)
    if limit > MAX_LIMIT:
        raise FieldError("/limit", "above_maximum", max=MAX_LIMIT)
    return limit


def parse_page_request(query: Mapping[str, str], scope: str) -> PageRequest:
    cursor = query.get("cursor")
    position = decode_cursor(cursor, scope) if cursor else None
    return PageRequest(position=position, limit=parse_limit(query.get("limit")))


def page_body[T](page: Page[T], scope: str, serialize: Callable[[T], object]) -> dict[str, object]:
    """Contract shape of every list endpoint: `{results, next_cursor}`."""
    next_cursor = encode_cursor(page.next_position, scope) if page.next_position is not None else None
    return {"results": [serialize(item) for item in page.results], "next_cursor": next_cursor}

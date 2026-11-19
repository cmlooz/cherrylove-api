"""Base domain errors (ADR-010 §3): each class carries a stable `code`, its HTTP `status` and `params`.

Use cases raise these after guard clauses; one handler maps them to RFC 9457 (F1.7). Codes come from the
contract's `ErrorCode` enum; field-level codes from `FieldErrorCode` (DEC-046).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar


class DomainError(Exception):
    code: ClassVar[str] = "internal_error"
    status: ClassVar[int] = 500
    default_params: ClassVar[Mapping[str, object]] = MappingProxyType({})

    def __init__(self, detail: str = "", **params: object) -> None:
        super().__init__(detail or self.code)
        self.detail = detail
        self.params: Mapping[str, object] = MappingProxyType({**self.default_params, **params})


class FieldError(DomainError):
    """Invalid input on one field; `pointer` is a JSON Pointer into the request (ADR-010 §1)."""

    code = "validation_failed"
    status = 400

    def __init__(self, pointer: str, field_code: str, detail: str = "", **params: object) -> None:
        super().__init__(detail, **params)
        self.pointer = pointer
        self.field_code = field_code


class NotFound(DomainError):
    """Missing **or not visible** to the actor: one code path, so existence never leaks (ADR-005 §4)."""

    code = "not_found"
    status = 404


class NotAuthor(DomainError):
    code = "not_author"
    status = 403


class EntityDeleted(DomainError):
    code = "entity_deleted"
    status = 410

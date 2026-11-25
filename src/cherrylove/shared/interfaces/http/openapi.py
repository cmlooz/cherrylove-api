"""drf-spectacular hooks: generated operations must follow the contract conventions (ADR-003 §5)."""

from __future__ import annotations

import re
from typing import Any

from drf_spectacular.openapi import AutoSchema

OPERATION_ID = re.compile(r"^[a-z]+(_[a-z]+){2,}$")


class OperationIdError(ValueError):
    """A view's operation ID breaks `<tag>_<verb>_<noun>`; set it with `extend_schema(operation_id=...)`."""


def enforce_operation_ids(result: dict[str, Any], generator: Any, request: Any, public: bool) -> dict[str, Any]:
    for path, item in result.get("paths", {}).items():
        for method, operation in item.items():
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            operation_id: str = operation["operationId"]
            tags: list[str] = operation.get("tags", [])
            if not OPERATION_ID.match(operation_id) or len(tags) != 1 or not operation_id.startswith(f"{tags[0]}_"):
                raise OperationIdError(f"{method.upper()} {path}: {operation_id!r} with tags {tags}")
    return result


class RequiredBodySchema(AutoSchema):
    """A PATCH body whose fields are all optional is still required by the contract (API-001)."""

    def _get_request_body(self, direction: str = "request") -> dict[str, Any] | None:
        body: dict[str, Any] | None = super()._get_request_body(direction)  # type: ignore[no-untyped-call]
        if body is not None:
            body["required"] = True
        return body

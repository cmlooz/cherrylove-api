"""Error responses straight from the approved contract (ADR-003, ADR-010, DEC-048).

Success bodies are generated from serializers, so the drift check really compares code with the contract.
Problem responses have one shape defined once in the contract (`components/responses`), so views declare them
by operation ID instead of re-describing each enum by hand. `include_contract_components` then copies the
contract components those schemas reference into the generated document.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse

CONTRACT_PATH = Path(settings.BASE_DIR) / "contract" / "openapi.v1.yaml"
PROBLEM_MEDIA_TYPE = "application/problem+json"
METHODS = ("get", "put", "post", "patch", "delete")


@cache
def contract() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    return loaded


def _operation(operation_id: str) -> dict[str, Any]:
    for item in contract()["paths"].values():
        for method in METHODS:
            operation = item.get(method)
            if operation and operation["operationId"] == operation_id:
                found: dict[str, Any] = operation
                return found
    raise KeyError(f"{operation_id} is not in the contract")


def error_responses(operation_id: str) -> dict[Any, OpenApiResponse]:
    """`extend_schema(responses=...)` entries for every 4xx/5xx the contract lists for the operation."""
    responses: dict[Any, OpenApiResponse] = {}
    for status, response in _operation(operation_id)["responses"].items():
        if not str(status).startswith(("4", "5")):
            continue
        component = contract()["components"]["responses"][response["$ref"].rsplit("/", 1)[-1]]
        schema = component["content"][PROBLEM_MEDIA_TYPE]["schema"]
        responses[(int(status), PROBLEM_MEDIA_TYPE)] = OpenApiResponse(
            response=schema, description=component["description"]
        )
    return responses


def error_headers(operation_id: str) -> list[OpenApiParameter]:
    """Response headers the contract declares on error responses (e.g. `Retry-After` on 429)."""
    headers: dict[str, tuple[dict[str, Any], list[int]]] = {}
    for status, response in _operation(operation_id)["responses"].items():
        if not str(status).startswith(("4", "5")):
            continue
        component = contract()["components"]["responses"][response["$ref"].rsplit("/", 1)[-1]]
        for name, header in component.get("headers", {}).items():
            headers.setdefault(name, (header["schema"], []))[1].append(int(status))
    return [
        OpenApiParameter(name, type=schema or OpenApiTypes.STR, location=OpenApiParameter.HEADER, response=statuses)
        for name, (schema, statuses) in headers.items()
    ]


def _refs(node: Any) -> set[str]:
    if isinstance(node, dict):
        found = {node["$ref"]} if isinstance(node.get("$ref"), str) else set()
        return found.union(*(_refs(value) for value in node.values()))
    if isinstance(node, list):
        return set().union(*(_refs(item) for item in node))
    return set()


def include_contract_components(result: dict[str, Any], generator: Any, request: Any, public: bool) -> dict[str, Any]:
    """drf-spectacular postprocessing hook: add contract schemas referenced but not generated."""
    schemas = result.setdefault("components", {}).setdefault("schemas", {})
    pending = _refs(result)
    while pending:
        ref = pending.pop()
        name = ref.rsplit("/", 1)[-1]
        if not ref.startswith("#/components/schemas/") or name in schemas:
            continue
        schemas[name] = contract()["components"]["schemas"][name]
        pending |= _refs(schemas[name])
    return result

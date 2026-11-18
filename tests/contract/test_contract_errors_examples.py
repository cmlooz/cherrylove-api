"""Contract completeness (IMPL-API-001 F0.8): narrowed error codes, examples, documented defaults,
FieldErrorCode (DEC-046), client-reported views (DEC-049) and media_asset sync changes (DEC-050)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC: dict[str, Any] = yaml.safe_load((ROOT / "contract" / "openapi.v1.yaml").read_text(encoding="utf-8"))
COMPONENTS: dict[str, Any] = SPEC["components"]
METHODS = {"get", "put", "post", "patch", "delete"}


def _resolve(node: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if ref is None:
        return node
    _, _, section, name = ref.split("/")
    resolved: dict[str, Any] = COMPONENTS[section][name]
    return resolved


def _operations() -> Iterator[tuple[str, dict[str, Any]]]:
    for item in SPEC["paths"].values():
        for method, operation in item.items():
            if method in METHODS:
                yield operation["operationId"], operation


def _media(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield from _resolve(node).get("content", {}).values()


def _has_example(media: dict[str, Any]) -> bool:
    if "example" in media or "examples" in media:
        return True
    schema = _resolve(media.get("schema", {}))
    return "examples" in schema or "example" in schema


def _code_enum(response: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    for media in _media(response):
        for part in media["schema"].get("allOf", []):
            codes.update(part.get("properties", {}).get("code", {}).get("enum", []))
    return codes


OPERATIONS = dict(_operations())


@pytest.mark.req("REQ-N-ARC-03")
@pytest.mark.parametrize("operation_id", sorted(OPERATIONS))
def test_every_4xx_declares_a_code_subset_of_error_code(operation_id: str) -> None:
    error_codes = set(COMPONENTS["schemas"]["ErrorCode"]["enum"])
    for status, response in OPERATIONS[operation_id]["responses"].items():
        if not status.startswith("4"):
            continue
        codes = _code_enum(response)
        assert codes, f"{operation_id} {status}: no narrowed code enum"
        assert codes <= error_codes, f"{operation_id} {status}: {codes - error_codes} not in ErrorCode"


@pytest.mark.req("REQ-N-ARC-03")
@pytest.mark.parametrize("operation_id", sorted(OPERATIONS))
def test_every_operation_has_an_example(operation_id: str) -> None:
    operation = OPERATIONS[operation_id]
    sources = [operation["requestBody"]] if "requestBody" in operation else []
    sources += list(operation["responses"].values())
    assert any(_has_example(media) for source in sources for media in _media(source)), operation_id


@pytest.mark.req("REQ-N-ARC-03")
def test_every_problem_response_example_uses_its_own_codes() -> None:
    for name, response in COMPONENTS["responses"].items():
        for media in _media(response):
            assert media["example"]["code"] in _code_enum(response), name


@pytest.mark.req("REQ-N-ARC-03")
def test_defaults_on_inputs_apply_on_create_only() -> None:
    for name, schema in COMPONENTS["schemas"].items():
        if not name.endswith("Input"):
            continue
        for field, prop in schema.get("properties", {}).items():
            if "default" in prop:
                assert "create only" in prop.get("description", ""), f"{name}.{field}"


@pytest.mark.req("REQ-N-ARC-03")
def test_field_errors_use_field_error_code() -> None:
    field_codes = COMPONENTS["schemas"]["FieldErrorCode"]
    assert field_codes["type"] == "string"
    assert {"required", "too_long", "invalid_format", "invalid_choice"} <= set(field_codes["enum"])
    error_item = COMPONENTS["schemas"]["Problem"]["properties"]["errors"]["items"]
    assert error_item["properties"]["code"] == {"$ref": "#/components/schemas/FieldErrorCode"}
    example = COMPONENTS["responses"]["ValidationFailed"]["content"]["application/problem+json"]["example"]
    assert all(error["code"] in field_codes["enum"] for error in example["errors"])


@pytest.mark.req("REQ-F-LOG-01")
def test_client_reported_views_endpoint_exists() -> None:
    operation = SPEC["paths"]["/views"]["post"]
    assert operation["operationId"] == "audit_record_views"
    view = COMPONENTS["schemas"]["ViewInput"]
    assert set(view["required"]) == {"id", "entity_type", "entity_id", "viewed_at"}
    assert set(view["properties"]) == {"id", "entity_type", "entity_id", "viewed_at"}, "metadata only, no content"
    assert "404" not in operation["responses"], "an invisible ID must not be revealed"


@pytest.mark.req("REQ-F-SYNC-10")
def test_sync_carries_media_asset_changes() -> None:
    assert "media_asset" in COMPONENTS["schemas"]["SyncEntityType"]["enum"]

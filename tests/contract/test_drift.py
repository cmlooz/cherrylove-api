"""The generated schema matches the approved contract per implemented operation (ADR-003 §2, DEC-048)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from drf_spectacular.generators import SchemaGenerator

from cherrylove.shared.interfaces.http.openapi import OperationIdError, enforce_operation_ids
from scripts.contract_drift import drift, load, read_pending

ROOT = Path(__file__).resolve().parents[2]


def _generated() -> dict[str, Any]:
    schema: dict[str, Any] = SchemaGenerator().get_schema(request=None, public=True)
    return schema


@pytest.mark.req("REQ-N-ARC-02")
def test_generated_schema_is_openapi_3_1_under_api_v1() -> None:
    schema = _generated()
    assert schema["openapi"] == "3.1.0"
    assert schema["servers"] == [{"url": "/api/v1"}]
    assert "/healthz" not in schema["paths"], "operational endpoint stays out of the contract"


@pytest.mark.req("REQ-N-ARC-03")
def test_generated_schema_has_no_drift_from_the_approved_contract() -> None:
    problems = drift(
        load(ROOT / "contract" / "openapi.v1.yaml"),
        _generated(),
        read_pending(ROOT / "contract" / "pending-operations.txt"),
    )
    assert problems == []


@pytest.mark.req("REQ-N-ARC-03")
@pytest.mark.parametrize(
    ("operation_id", "tags"),
    [("retrieveCard", ["cards"]), ("cards_get", ["cards"]), ("memories_get_card", ["cards"]), ("cards_get_card", [])],
)
def test_operation_id_hook_rejects_off_convention_ids(operation_id: str, tags: list[str]) -> None:
    result = {"paths": {"/cards/{id}": {"get": {"operationId": operation_id, "tags": tags}}}}
    with pytest.raises(OperationIdError):
        enforce_operation_ids(result, None, None, public=True)


@pytest.mark.req("REQ-N-ARC-03")
def test_operation_id_hook_accepts_contract_ids() -> None:
    result = {"paths": {"/cards/{id}": {"get": {"operationId": "cards_get_card", "tags": ["cards"]}}}}
    assert enforce_operation_ids(result, None, None, public=True) is result

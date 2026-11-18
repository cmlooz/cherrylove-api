"""Unit tests for the contract drift check (ADR-003 §2, DEC-048)."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from scripts.contract_drift import drift, normalize, operations


def _spec(schema_name: str = "Card", enum: list[str] | None = None, *, extra_op: bool = False) -> dict[str, Any]:
    paths: dict[str, Any] = {
        "/cards/{card_id}": {
            "parameters": [{"name": "card_id", "in": "path", "required": True, "schema": {"type": "string"}}],
            "get": {
                "tags": ["cards"],
                "operationId": "cards_get_card",
                "summary": "Card detail",
                "responses": {
                    "200": {
                        "description": "Card.",
                        "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{schema_name}"}}},
                    }
                },
            },
        }
    }
    if extra_op:
        paths["/cards/mine"] = {
            "get": {"tags": ["cards"], "operationId": "cards_list_mine", "responses": {"200": {"description": "ok"}}}
        }
    return {
        "openapi": "3.1.0",
        "paths": paths,
        "components": {
            "schemas": {
                schema_name: {
                    "type": "object",
                    "required": ["id", "mode"],
                    "properties": {"id": {"type": "string"}, "mode": {"enum": enum or ["today", "random_past"]}},
                }
            }
        },
    }


@pytest.mark.req("REQ-N-ARC-03")
def test_ref_names_key_order_enum_order_and_prose_do_not_matter() -> None:
    approved = _spec("Card", ["today", "random_past"])
    generated = _spec("CardOutput", ["random_past", "today"])
    generated_op = generated["paths"]["/cards/{card_id}"]["get"]
    generated_op["summary"] = "Something else"
    generated["paths"]["/cards/{card_id}"]["get"] = dict(reversed(list(generated_op.items())))
    assert operations(approved) == operations(generated)
    assert drift(approved, generated, pending=set()) == []


@pytest.mark.req("REQ-N-ARC-03")
def test_a_changed_wire_shape_is_drift() -> None:
    generated = _spec()
    generated["components"]["schemas"]["Card"]["properties"]["id"]["type"] = "integer"
    assert drift(_spec(), generated, pending=set()) == ["cards_get_card: differs from the approved contract"]


@pytest.mark.req("REQ-N-ARC-03")
def test_an_operation_outside_the_contract_fails() -> None:
    problems = drift(_spec(), _spec(extra_op=True), pending=set())
    assert problems == ["cards_list_mine: implemented but not in the approved contract"]


@pytest.mark.req("REQ-N-ARC-03")
def test_unbuilt_operations_must_be_pending_and_pending_must_be_real() -> None:
    approved = _spec(extra_op=True)
    assert drift(approved, _spec(), pending=set()) == ["cards_list_mine: not implemented and not listed as pending"]
    assert drift(approved, _spec(), pending={"cards_list_mine"}) == []
    assert drift(approved, _spec(), pending={"cards_list_mine", "cards_get_card"}) == [
        "cards_get_card: implemented but still listed as pending"
    ]
    assert drift(approved, _spec(), pending={"cards_list_mine", "ghost_get_thing"}) == [
        "ghost_get_thing: listed as pending but not in the approved contract"
    ]


@pytest.mark.req("REQ-N-ARC-03")
def test_pending_list_may_only_shrink() -> None:
    approved = _spec(extra_op=True)
    assert drift(approved, _spec(extra_op=True), pending=set(), base_pending={"cards_list_mine"}) == []
    assert drift(approved, _spec(), pending={"cards_list_mine"}, base_pending=set()) == [
        "cards_list_mine: added to pending-operations.txt (the list may only shrink)"
    ]


@pytest.mark.req("REQ-N-ARC-03")
def test_recursive_refs_terminate() -> None:
    spec: dict[str, Any] = {"components": {"schemas": {"Node": {"properties": {"child": {"$ref": "#/components/schemas/Node"}}}}}}
    result = normalize(copy.deepcopy(spec), {"$ref": "#/components/schemas/Node"})
    assert result == {"properties": {"child": {"$recursive": "Node"}}}

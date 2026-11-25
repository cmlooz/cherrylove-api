"""Contract drift check (ADR-003 §2, DEC-048).

The generated OpenAPI (drf-spectacular) must equal the approved contract for every implemented operation;
an operation the contract does not define fails; an approved operation that is not implemented yet must be
listed in contract/pending-operations.txt, a list that may only shrink.

Operations are compared on their wire shape: tags, parameters, request body and responses (status, media
type, schema). Prose (summary, description, examples) is ignored. Normalization makes key order, `$ref`
component names and enum order irrelevant.

    python scripts/contract_drift.py --approved contract/openapi.v1.yaml --generated generated.yaml \
        --pending contract/pending-operations.txt [--base-pending base-pending.txt]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

METHODS = ("get", "put", "post", "patch", "delete")
PROSE = frozenset({"summary", "description", "example", "examples", "title", "externalDocs", "deprecated"})

type Json = Any


def load(path: Path) -> dict[str, Json]:
    data: dict[str, Json] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def read_pending(path: Path) -> set[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")}


def _resolve_ref(spec: dict[str, Json], ref: str) -> Json:
    if not ref.startswith("#/"):
        raise ValueError(f"only local $ref is supported: {ref}")
    node: Json = spec
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def normalize(spec: dict[str, Json], node: Json, seen: tuple[str, ...] = ()) -> Json:
    """Inline every $ref, drop prose, sort keys and enum values."""
    if isinstance(node, list):
        return [normalize(spec, item, seen) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        ref = node["$ref"]
        if ref in seen:
            return {"$recursive": ref.rsplit("/", 1)[-1]}
        siblings = {k: v for k, v in node.items() if k != "$ref"}
        merged = {**_resolve_ref(spec, ref), **siblings}
        return normalize(spec, merged, (*seen, ref))
    result: dict[str, Json] = {}
    for key in sorted(node):
        if key in PROSE:
            continue
        value = normalize(spec, node[key], seen)
        if key in {"enum", "required", "tags"} and isinstance(value, list):
            value = sorted(value, key=lambda item: json.dumps(item, sort_keys=True))
        result[key] = value
    return result


def operations(spec: dict[str, Json]) -> dict[str, Json]:
    """operationId → normalized wire shape, including method and path."""
    found: dict[str, Json] = {}
    for path, item in spec.get("paths", {}).items():
        shared_parameters = item.get("parameters", [])
        for method in METHODS:
            operation = item.get(method)
            if operation is None:
                continue
            operation_id = operation["operationId"]
            if operation_id in found:
                raise ValueError(f"duplicated operationId {operation_id}")
            parameters = normalize(spec, [*shared_parameters, *operation.get("parameters", [])])
            for parameter in parameters:
                parameter.setdefault("required", False)  # OpenAPI default: omitted == false
            found[operation_id] = {
                "method": method,
                "path": path,
                "tags": normalize(spec, operation.get("tags", [])),
                "parameters": sorted(parameters, key=lambda p: (p.get("in", ""), p.get("name", ""))),
                "requestBody": normalize(spec, operation.get("requestBody")),
                "responses": normalize(spec, operation.get("responses", {})),
                # Effective security: an omitted requirement and an explicit [] both mean "no auth".
                "security": operation.get("security", spec.get("security")) or [],
            }
    return found


def drift(
    approved: dict[str, Json],
    generated: dict[str, Json],
    pending: set[str],
    base_pending: set[str] | None = None,
) -> list[str]:
    """Every problem found; an empty list means no drift."""
    approved_ops = operations(approved)
    generated_ops = operations(generated)
    problems: list[str] = []
    for operation_id in sorted(set(generated_ops) - set(approved_ops)):
        problems.append(f"{operation_id}: implemented but not in the approved contract")
    for operation_id in sorted(set(generated_ops) & set(approved_ops)):
        if generated_ops[operation_id] != approved_ops[operation_id]:
            problems.append(f"{operation_id}: differs from the approved contract")
        if operation_id in pending:
            problems.append(f"{operation_id}: implemented but still listed as pending")
    for operation_id in sorted(set(approved_ops) - set(generated_ops) - pending):
        problems.append(f"{operation_id}: not implemented and not listed as pending")
    for operation_id in sorted(pending - set(approved_ops)):
        problems.append(f"{operation_id}: listed as pending but not in the approved contract")
    if base_pending is not None:
        for operation_id in sorted(pending - base_pending):
            problems.append(f"{operation_id}: added to pending-operations.txt (the list may only shrink)")
    return problems


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--approved", type=Path, required=True)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--pending", type=Path, required=True)
    parser.add_argument("--base-pending", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    base = read_pending(args.base_pending) if args.base_pending else None
    problems = drift(load(args.approved), load(args.generated), read_pending(args.pending), base)
    for problem in problems:
        print(f"drift: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The approved contract lives in contract/ unchanged (ADR-003 §1, §5). Parsed line by line on purpose."""

from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contract" / "openapi.v1.yaml"
SOURCE = tomllib.loads((ROOT / "contract" / "source.toml").read_text(encoding="utf-8"))

HTTP_METHOD = re.compile(r"^    (get|put|post|patch|delete|head|options):\s*$")
TAGS = re.compile(r"^      tags: \[(?P<tags>[^\]]*)\]\s*$")
OPERATION_ID = re.compile(r"^      operationId: (?P<id>\S+)\s*$")
SNAKE_PARTS = re.compile(r"^[a-z]+(_[a-z]+){2,}$")


def _operations() -> list[tuple[int, list[str], str | None]]:
    """(line number, tags, operationId) for every operation under `paths`."""
    operations: list[tuple[int, list[str], str | None]] = []
    in_paths = False
    for number, line in enumerate(CONTRACT.read_text(encoding="utf-8").splitlines(), start=1):
        if line and not line.startswith(" "):
            in_paths = line.startswith("paths:")
            continue
        if not in_paths:
            continue
        if HTTP_METHOD.match(line):
            operations.append((number, [], None))
        elif operations and (tags := TAGS.match(line)):
            operations[-1][1].extend(t.strip() for t in tags["tags"].split(","))
        elif operations and (operation := OPERATION_ID.match(line)):
            operations[-1] = (operations[-1][0], operations[-1][1], operation["id"])
    return operations


@pytest.mark.req("REQ-N-ARC-03")
def test_contract_is_the_last_approved_version() -> None:
    """Unreviewed edits fail: an approved change records its hash in contract/source.toml (ADR-003 §1)."""
    assert hashlib.sha256(CONTRACT.read_bytes()).hexdigest() == SOURCE["approved"][-1]["sha256"]
    assert b"\r\n" not in CONTRACT.read_bytes()


@pytest.mark.req("REQ-N-ARC-03")
def test_contract_is_openapi_3_1() -> None:
    first = CONTRACT.read_text(encoding="utf-8").splitlines()[0]
    assert re.fullmatch(r"openapi: 3\.1\.\d+", first), first


@pytest.mark.req("REQ-N-ARC-03")
def test_operation_ids_follow_tag_verb_noun() -> None:
    operations = _operations()
    assert len(operations) >= 40, "operation parser found too few operations"
    seen: set[str] = set()
    for number, tags, operation_id in operations:
        assert operation_id, f"line {number}: operation without operationId"
        assert len(tags) == 1, f"{operation_id}: exactly one tag expected, got {tags}"
        assert SNAKE_PARTS.match(operation_id), f"{operation_id}: not <tag>_<verb>_<noun>"
        assert operation_id.startswith(f"{tags[0]}_"), f"{operation_id}: prefix is not its tag {tags[0]}"
        assert operation_id not in seen, f"{operation_id}: duplicated"
        seen.add(operation_id)

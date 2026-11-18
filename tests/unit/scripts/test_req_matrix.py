"""Unit tests for the REQ → tests matrix (ADR-014 §6, REQ-N-QA-06)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.req_matrix import check, collect, matrix, read_catalog

CATALOG = {"REQ-F-CARD-07", "REQ-N-QA-06"}


@pytest.mark.req("REQ-N-QA-06")
def test_catalog_reads_ids_from_markdown_table_rows(tmp_path: Path) -> None:
    doc = tmp_path / "functional.md"
    doc.write_text(
        "| ID | Requirement |\n|----|----|\n| REQ-F-CARD-07 | Published card is read-only. |\n"
        "Mentions REQ-F-CARD-99 in prose only.\n",
        encoding="utf-8",
    )
    assert read_catalog([doc]) == {"REQ-F-CARD-07"}


@pytest.mark.req("REQ-N-QA-06")
def test_known_markers_pass() -> None:
    assert check({"tests/a.py::t": ["REQ-F-CARD-07"]}, CATALOG) == []


@pytest.mark.req("REQ-N-QA-06")
@pytest.mark.parametrize(
    ("ids", "expected"),
    [
        ([], "tests/a.py::t: no @pytest.mark.req marker"),
        (["REQ-F-CARD-99"], "tests/a.py::t: unknown requirement REQ-F-CARD-99"),
        (["DEC-023"], "tests/a.py::t: malformed requirement ID 'DEC-023'"),
    ],
)
def test_missing_unknown_or_malformed_markers_fail(ids: list[str], expected: str) -> None:
    assert check({"tests/a.py::t": ids}, CATALOG) == [expected]


@pytest.mark.req("REQ-N-QA-06")
def test_matrix_lists_every_catalog_requirement_and_its_tests() -> None:
    table = matrix({"tests/a.py::t[1]": ["REQ-F-CARD-07"], "tests/a.py::t[2]": ["REQ-F-CARD-07"]}, CATALOG)
    assert "| REQ-F-CARD-07 | tests/a.py::t |" in table
    assert "| REQ-N-QA-06 | — |" in table
    assert "1 of 2 catalog requirements have at least one test." in table


@pytest.mark.req("REQ-N-QA-06")
def test_collect_reads_req_markers_from_real_tests() -> None:
    cited = collect(["tests/unit/scripts/test_req_matrix.py"])
    assert cited
    assert all(ids == ["REQ-N-QA-06"] for ids in cited.values())

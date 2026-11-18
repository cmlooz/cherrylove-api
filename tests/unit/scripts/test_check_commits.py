"""Unit tests for the commit and PR traceability check (REQ-N-QA-06)."""

from __future__ import annotations

import pytest

from scripts.check_commits import Commit, check_commit, check_pr_body

SHA = "0123456789abcdef"


@pytest.mark.req("REQ-N-QA-06")
@pytest.mark.parametrize(
    "subject",
    ["feat(cards): add card entity", "fix: handle empty body", "build!: drop python 3.13", "ci(github): pin actions"],
)
def test_conventional_subject_with_an_id_passes(subject: str) -> None:
    assert check_commit(Commit(SHA, f"{subject}\n\nRefs: REQ-F-CARD-07")) == []


@pytest.mark.req("REQ-N-QA-06")
@pytest.mark.parametrize(
    "subject",
    ["Add card entity", "feature(cards): add", "feat(Cards): add", "feat:add", "feat(cards): ", "WIP"],
)
def test_non_conventional_subject_fails(subject: str) -> None:
    problems = check_commit(Commit(SHA, f"{subject}\n\nRefs: DEC-023"))
    assert problems
    assert "Conventional Commit" in problems[0]


@pytest.mark.req("REQ-N-QA-06")
@pytest.mark.parametrize("trace", ["REQ-N-QA-06", "DEC-023", "ADR-015", "DATA-001", "IMPL-API-001"])
def test_any_trace_id_satisfies_the_message(trace: str) -> None:
    assert check_commit(Commit(SHA, f"chore: tidy\n\nRefs: {trace}")) == []


@pytest.mark.req("REQ-N-QA-06")
@pytest.mark.parametrize("message", ["chore: tidy", "chore: tidy\n\nRefs: REQ-CARD-7, DEC-23"])
def test_message_without_a_valid_id_fails(message: str) -> None:
    assert check_commit(Commit(SHA, message)) == ["0123456: message cites no REQ/DEC/ADR/DATA/IMPL ID"]


@pytest.mark.req("REQ-N-QA-06")
def test_fixup_commits_are_rejected() -> None:
    problems = check_commit(Commit(SHA, "fixup! feat(cards): add card entity\n\nREQ-F-CARD-07"))
    assert problems == ["0123456: fixup/squash commit must be squashed before merge"]


@pytest.mark.req("REQ-N-QA-06")
def test_pr_body_needs_traceability_section_and_a_req_id() -> None:
    assert check_pr_body("## Traceability (required)\n\n- Requirements: REQ-N-OPS-01\n") == []
    assert check_pr_body("## What and why\n\nStuff. DEC-023") == [
        "PR body: missing the '## Traceability' section of the template",
        "PR body: cites no REQ ID",
    ]

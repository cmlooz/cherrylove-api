"""Unit tests for the commit and PR traceability check (REQ-N-QA-06)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_commits import DEPENDABOT_EMAIL, Commit, check_commit, check_pr_body, main

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


BUMP = "build(deps): Bump astral-sh/setup-uv from 10.3.3 to 10.4.0 in the actions group across 1 directory"


@pytest.mark.req("REQ-N-QA-06")
def test_a_dependabot_commit_is_traced_to_adr_015_but_keeps_the_subject_rule() -> None:
    assert check_commit(Commit(SHA, BUMP, DEPENDABOT_EMAIL), dependency_update=True) == []
    assert check_commit(Commit(SHA, BUMP, DEPENDABOT_EMAIL)), "without the flag the ID rule applies"
    assert check_commit(Commit(SHA, "Bump things", DEPENDABOT_EMAIL), dependency_update=True)


@pytest.mark.req("REQ-N-QA-06")
@pytest.mark.parametrize(
    "case",
    [
        ("dependabot[bot]", DEPENDABOT_EMAIL, 0),
        ("dependabot[bot]", "camilo@example.com", 1),  # a human commit on a bot PR still needs an ID
        ("cmlooz", DEPENDABOT_EMAIL, 3),  # a human PR never skips, whatever the commit author says
    ],
)
def test_only_dependabot_commits_on_dependabot_prs_skip_the_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], case: tuple[str, str, int]
) -> None:
    author, email, failures = case
    monkeypatch.setattr("scripts.check_commits.commits_in", lambda _: [Commit(SHA, BUMP, email)])
    body = tmp_path / "body.md"
    body.write_text("Bumps setup-uv.", encoding="utf-8")
    code = main(["--range", "a..b", "--pr-body-file", str(body), "--pr-author", author])
    assert code == (1 if failures else 0)
    assert capsys.readouterr().err.count("traceability:") == failures

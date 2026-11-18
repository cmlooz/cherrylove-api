"""Commit and PR traceability check (REQ-N-QA-06, DEC-023, ADR-015 §1).

Every commit: Conventional Commits subject and at least one REQ/DEC/ADR/DATA/IMPL ID in its message.
The PR body: at least one REQ ID and the template's traceability section.

    python scripts/check_commits.py --range origin/main..HEAD [--pr-body-file body.md]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

TYPES = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert")
SUBJECT = re.compile(rf"^(?:{'|'.join(TYPES)})(?:\([a-z0-9][a-z0-9-]*\))?!?: \S.{{0,99}}$")
TRACE_ID = re.compile(r"\b(?:REQ-[FN]-[A-Z]+-\d{2}|DEC-\d{3}|ADR-\d{3}|DATA-\d{3}|API-\d{3}|IMPL-[A-Z]+-\d{3})\b")
REQ_ID = re.compile(r"\bREQ-[FN]-[A-Z]+-\d{2}\b")
SEPARATOR = "\x1e"


@dataclass(frozen=True)
class Commit:
    sha: str
    message: str

    @property
    def subject(self) -> str:
        return self.message.split("\n", 1)[0]


def check_commit(commit: Commit) -> list[str]:
    problems: list[str] = []
    short = commit.sha[:7]
    if commit.subject.startswith(("fixup!", "squash!")):
        problems.append(f"{short}: fixup/squash commit must be squashed before merge")
    elif not SUBJECT.match(commit.subject):
        problems.append(f"{short}: subject is not a Conventional Commit: {commit.subject!r}")
    if not TRACE_ID.search(commit.message):
        problems.append(f"{short}: message cites no REQ/DEC/ADR/DATA/IMPL ID")
    return problems


def check_pr_body(body: str) -> list[str]:
    problems: list[str] = []
    if "## Traceability" not in body:
        problems.append("PR body: missing the '## Traceability' section of the template")
    if not REQ_ID.search(body):
        problems.append("PR body: cites no REQ ID")
    return problems


def commits_in(revision_range: str) -> list[Commit]:
    output = subprocess.run(
        ["git", "log", "--no-merges", f"--format=%H%n%B{SEPARATOR}", revision_range],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    ).stdout
    commits: list[Commit] = []
    for raw in output.split(SEPARATOR):
        chunk = raw.strip("\n")
        if not chunk:
            continue
        sha, _, message = chunk.partition("\n")
        commits.append(Commit(sha, message.strip()))
    return commits


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--range", dest="revision_range", required=True)
    parser.add_argument("--pr-body-file", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    commits = commits_in(args.revision_range)
    problems = [problem for commit in commits for problem in check_commit(commit)]
    if not commits:
        problems.append(f"no commits in {args.revision_range}")
    if args.pr_body_file:
        problems += check_pr_body(args.pr_body_file.read_text(encoding="utf-8"))
    for problem in problems:
        print(f"traceability: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

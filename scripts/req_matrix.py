"""REQ → tests matrix from `@pytest.mark.req` markers (ADR-014 §6, REQ-N-QA-06).

Fails when a test has no `req` marker, or a marker cites an ID that is malformed or absent from the frozen
requirement catalogs (functional.md / nfr.md of cherryLove-docs). Writes the matrix as Markdown.

    python scripts/req_matrix.py --catalog ../cherryLove-docs/02-requirements/functional.md \
        --catalog ../cherryLove-docs/02-requirements/nfr.md --output req-matrix.md [pytest args...]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import pytest

REQ_ID = re.compile(r"^REQ-[FN]-[A-Z]+-\d{2}$")
CATALOG_ROW = re.compile(r"^\|\s*(REQ-[FN]-[A-Z]+-\d{2})\s*\|", re.MULTILINE)


def read_catalog(paths: Iterable[Path]) -> set[str]:
    return {match for path in paths for match in CATALOG_ROW.findall(path.read_text(encoding="utf-8"))}


class _Collector:
    """pytest plugin: records (test node id, cited REQ IDs) at collection time."""

    def __init__(self) -> None:
        self.cited: dict[str, list[str]] = {}

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        for item in items:
            self.cited[item.nodeid] = [str(arg) for marker in item.iter_markers("req") for arg in marker.args]


def collect(pytest_args: list[str]) -> dict[str, list[str]]:
    collector = _Collector()
    code = pytest.main(["--collect-only", "-qq", "-p", "no:cacheprovider", *pytest_args], plugins=[collector])
    if code not in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
        raise SystemExit(f"test collection failed with exit code {code}")
    return collector.cited


def check(cited: dict[str, list[str]], catalog: set[str]) -> list[str]:
    problems: list[str] = []
    for node, ids in sorted(cited.items()):
        if not ids:
            problems.append(f"{node}: no @pytest.mark.req marker")
        for req in ids:
            if not REQ_ID.match(req):
                problems.append(f"{node}: malformed requirement ID {req!r}")
            elif req not in catalog:
                problems.append(f"{node}: unknown requirement {req}")
    return problems


def matrix(cited: dict[str, list[str]], catalog: set[str]) -> str:
    by_req: dict[str, list[str]] = defaultdict(list)
    for node, ids in cited.items():
        for req in ids:
            by_req[req].append(node)
    lines = ["# REQ → tests matrix", "", "| REQ | Tests |", "|-----|-------|"]
    for req in sorted(catalog | set(by_req)):
        tests = sorted({node.split("[", 1)[0] for node in by_req.get(req, [])})
        lines.append(f"| {req} | {'<br>'.join(tests) if tests else '—'} |")
    covered = len([req for req in catalog if by_req.get(req)])
    lines += ["", f"{covered} of {len(catalog)} catalog requirements have at least one test."]
    return "\n".join(lines) + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path)
    args, pytest_args = parser.parse_known_args(list(argv) if argv is not None else None)
    catalog = read_catalog(args.catalog)
    if not catalog:
        print("req-matrix: catalog has no REQ IDs", file=sys.stderr)
        return 1
    cited = collect(pytest_args)
    problems = check(cited, catalog)
    for problem in problems:
        print(f"req-matrix: {problem}", file=sys.stderr)
    if args.output:
        args.output.write_text(matrix(cited, catalog), encoding="utf-8", newline="\n")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

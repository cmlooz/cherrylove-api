"""`.unscoped` is used only in backoffice/infrastructure and migrations (ADR-005 §3, REQ-N-SEC-01)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = ("src/cherrylove/backoffice/infrastructure/",)


def unscoped_uses(source: str) -> list[int]:
    """Line numbers of every `<expr>.unscoped` attribute access (declarations `unscoped = ...` are fine)."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute) and node.attr == "unscoped"
    ]


def _offenders(root: Path) -> list[str]:
    found: list[str] = []
    for path in sorted((root / "src").rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if relative.startswith(ALLOWED) or "/migrations/" in relative:
            continue
        found += [f"{relative}:{line}" for line in unscoped_uses(path.read_text(encoding="utf-8"))]
    return found


@pytest.mark.req("REQ-N-SEC-01")
def test_unscoped_appears_only_in_backoffice_infrastructure() -> None:
    assert _offenders(ROOT) == []


@pytest.mark.req("REQ-N-SEC-01")
def test_the_check_bites(tmp_path: Path) -> None:
    for folder in ["cards/infrastructure", "backoffice/infrastructure"]:
        target = tmp_path / "src" / "cherrylove" / folder
        target.mkdir(parents=True)
        (target / "repo.py").write_text("rows = Card.unscoped.all()\nunscoped = None\n", encoding="utf-8")
    assert _offenders(tmp_path) == ["src/cherrylove/cards/infrastructure/repo.py:1"]

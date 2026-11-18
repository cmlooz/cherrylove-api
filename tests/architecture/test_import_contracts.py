"""Architecture fitness functions: import-linter contracts hold and actually bite (ADR-001 §6)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "cherrylove"
MODULES = [
    "identity", "cards", "memories", "media", "diary", "favorites",
    "notifications", "sync", "audit", "backoffice", "shared",
]  # fmt: skip
LAYERS = ["domain", "application", "infrastructure", "interfaces"]
LINT_IMPORTS = Path(sys.executable).with_name("lint-imports")


def _lint_imports(src_root: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(src_root)}
    return subprocess.run(
        [str(LINT_IMPORTS), "--config", str(ROOT / ".importlinter"), "--no-cache"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.req("REQ-N-ARC-01")
def test_import_contracts_pass() -> None:
    result = _lint_imports(ROOT / "src")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.parametrize("module", MODULES)
def test_every_module_has_the_four_layers(module: str) -> None:
    for layer in LAYERS:
        assert (SRC / module / layer / "__init__.py").is_file(), f"{module}/{layer} is missing"


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.parametrize(
    ("offender", "source", "contract"),
    [
        ("cards/domain/leak.py", "import django.db\n", "Domain is plain Python"),
        ("cards/application/leak.py", "import cherrylove.memories.domain\n", "Modules talk only through"),
        ("cards/interfaces/leak.py", "import cherrylove.cards.infrastructure\n", "Layers inside every module"),
        ("shared/domain/leak.py", "import cherrylove.cards.application.public\n", "shared kernel"),
    ],
)
def test_a_violation_is_reported(tmp_path: Path, offender: str, source: str, contract: str) -> None:
    copy = tmp_path / "cherrylove"
    shutil.copytree(SRC, copy, ignore=shutil.ignore_patterns("__pycache__"))
    target = copy / offender
    target.parent.mkdir(parents=True, exist_ok=True)
    (target.parent / "public.py").touch()
    target.write_text(source, encoding="utf-8")
    result = _lint_imports(tmp_path)
    assert result.returncode != 0
    assert contract in result.stdout
    assert "BROKEN" in result.stdout

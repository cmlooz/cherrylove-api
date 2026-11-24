"""Dependabot never proposes leaving the pinned Django LTS line (ADR-016 Decision 1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _uv_update() -> dict[str, Any]:
    config: dict[str, Any] = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    updates: list[dict[str, Any]] = config["updates"]
    return next(u for u in updates if u["package-ecosystem"] == "uv")


@pytest.mark.req("REQ-N-QA-05")
def test_django_major_and_minor_updates_are_ignored() -> None:
    rules = [r for r in _uv_update().get("ignore", []) if r["dependency-name"] == "django"]
    assert len(rules) == 1
    assert set(rules[0]["update-types"]) == {"version-update:semver-major", "version-update:semver-minor"}


@pytest.mark.req("REQ-N-QA-05")
def test_django_patch_updates_still_flow() -> None:
    rules = [r for r in _uv_update().get("ignore", []) if r["dependency-name"] == "django"]
    assert "version-update:semver-patch" not in rules[0]["update-types"]

"""The toolchain is reproducible: exact interpreter and exact locked versions (ADR-016)."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> dict[str, Any]:
    return tomllib.loads((ROOT / name).read_text(encoding="utf-8"))


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_name(spec: str) -> str:
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", spec)
    assert match, spec
    return _normalize(match.group(0))


def _pins() -> dict[str, str]:
    pins = _load("pins.toml")
    return {_normalize(k): v for k, v in {**pins["runtime"], **pins["dev"]}.items()}


def _direct_requirements() -> list[str]:
    project = _load("pyproject.toml")
    groups: dict[str, list[str]] = project.get("dependency-groups", {})
    return list(project["project"]["dependencies"]) + [spec for specs in groups.values() for spec in specs]


@pytest.mark.req("REQ-N-QA-05")
def test_interpreter_is_the_pinned_python() -> None:
    pinned = _load("pins.toml")["python"]["version"]
    running = ".".join(str(part) for part in sys.version_info[:3])
    assert running == pinned
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == pinned


@pytest.mark.req("REQ-N-QA-05")
def test_every_direct_dependency_is_declared_with_its_exact_pin() -> None:
    pins = _pins()
    for spec in _direct_requirements():
        name = _requirement_name(spec)
        assert name in pins, f"{name} has no pin in pins.toml"
        assert spec.split(";")[0].endswith(f"=={pins[name]}"), spec


@pytest.mark.req("REQ-N-QA-05")
def test_lockfile_resolves_every_direct_dependency_to_its_pin() -> None:
    pins = _pins()
    locked = {_normalize(p["name"]): p["version"] for p in _load("uv.lock")["package"] if "version" in p}
    direct = {_requirement_name(spec) for spec in _direct_requirements()}
    assert direct, "no direct dependencies found"
    for name in direct:
        assert locked.get(name) == pins[name], f"{name}: locked {locked.get(name)} != pin {pins[name]}"

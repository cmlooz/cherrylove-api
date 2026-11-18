"""The contract asset is published as YAML and JSON with the same content (ADR-003 §3, DEC-044)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.contract_json import export, load_yaml, main, same_content, version

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contract" / "openapi.v1.yaml"


@pytest.mark.req("REQ-N-ARC-03")
def test_json_asset_parses_to_the_same_content_as_yaml(tmp_path: Path) -> None:
    target = tmp_path / "openapi.v1.json"
    assert main(["export", str(CONTRACT), str(target)]) == 0
    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert parsed == load_yaml(CONTRACT)
    assert main(["check", str(CONTRACT), str(target)]) == 0


@pytest.mark.req("REQ-N-ARC-03")
def test_civil_dates_stay_strings_in_json(tmp_path: Path) -> None:
    target = tmp_path / "openapi.v1.json"
    export(CONTRACT, target)
    assert '"2026-10-31"' in target.read_text(encoding="utf-8")


@pytest.mark.req("REQ-N-ARC-03")
def test_a_different_json_asset_is_detected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "openapi.v1.json"
    export(CONTRACT, target)
    data = json.loads(target.read_text(encoding="utf-8"))
    data["info"]["version"] = "9.9.9"
    target.write_text(json.dumps(data), encoding="utf-8")
    assert not same_content(CONTRACT, target)
    assert main(["check", str(CONTRACT), str(target)]) == 1
    assert "differ" in capsys.readouterr().err


@pytest.mark.req("REQ-N-ARC-03")
def test_release_version_comes_from_info_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert version(CONTRACT) == "1.0.0"
    assert main(["version", str(CONTRACT)]) == 0
    assert capsys.readouterr().out.strip() == "1.0.0"


@pytest.mark.req("REQ-N-ARC-03")
def test_export_and_check_need_a_json_path() -> None:
    with pytest.raises(SystemExit):
        main(["export", str(CONTRACT)])

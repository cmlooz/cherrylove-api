"""The scripts' command-line entry points, as CI calls them (REQ-N-QA-06, ADR-003 §2)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import check_commits, contract_drift, req_matrix

APPROVED = {
    "openapi": "3.1.0",
    "paths": {
        "/cards/mine": {"get": {"tags": ["cards"], "operationId": "cards_list_mine", "responses": {"200": {}}}},
    },
}


def _write_yaml(path: Path, data: object) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


@pytest.mark.req("REQ-N-ARC-03")
def test_drift_cli_passes_when_unbuilt_operations_are_pending(tmp_path: Path) -> None:
    approved = _write_yaml(tmp_path / "approved.yaml", APPROVED)
    generated = _write_yaml(tmp_path / "generated.yaml", {"openapi": "3.1.0", "paths": {}})
    pending = tmp_path / "pending.txt"
    pending.write_text("# comment\ncards_list_mine\n", encoding="utf-8")
    args = ["--approved", str(approved), "--generated", str(generated), "--pending", str(pending)]
    assert contract_drift.main(args) == 0
    assert contract_drift.main([*args, "--base-pending", str(pending)]) == 0


@pytest.mark.req("REQ-N-ARC-03")
def test_drift_cli_fails_and_reports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    approved = _write_yaml(tmp_path / "approved.yaml", APPROVED)
    generated = _write_yaml(tmp_path / "generated.yaml", {"openapi": "3.1.0", "paths": {}})
    pending = tmp_path / "pending.txt"
    pending.write_text("", encoding="utf-8")
    assert (
        contract_drift.main(["--approved", str(approved), "--generated", str(generated), "--pending", str(pending)])
        == 1
    )
    assert "cards_list_mine: not implemented and not listed as pending" in capsys.readouterr().err


@pytest.mark.req("REQ-N-ARC-03")
def test_drift_rejects_remote_refs() -> None:
    spec = {"paths": {}, "x": {"$ref": "https://example.com/schema.yaml"}}
    with pytest.raises(ValueError, match="only local"):
        contract_drift.normalize(spec, spec["x"])


@pytest.mark.req("REQ-N-ARC-03")
def test_drift_rejects_duplicated_operation_ids() -> None:
    spec = {
        "paths": {
            "/a": {"get": {"operationId": "cards_get_card"}},
            "/b": {"get": {"operationId": "cards_get_card"}},
        }
    }
    with pytest.raises(ValueError, match="duplicated"):
        contract_drift.operations(spec)


@pytest.mark.req("REQ-N-QA-06")
def test_req_matrix_cli_writes_the_matrix(tmp_path: Path) -> None:
    catalog = tmp_path / "nfr.md"
    catalog.write_text("| REQ-N-QA-06 | Traceability |\n", encoding="utf-8")
    output = tmp_path / "matrix.md"
    code = req_matrix.main(
        ["--catalog", str(catalog), "--output", str(output), "tests/unit/scripts/test_req_matrix.py"]
    )
    assert code == 0
    assert "| REQ-N-QA-06 | tests/unit/scripts/test_req_matrix.py::" in output.read_text(encoding="utf-8")


@pytest.mark.req("REQ-N-QA-06")
def test_req_matrix_cli_fails_on_unknown_requirements(tmp_path: Path) -> None:
    catalog = tmp_path / "functional.md"
    catalog.write_text("| REQ-F-CARD-07 | Read-only |\n", encoding="utf-8")
    assert req_matrix.main(["--catalog", str(catalog), "tests/unit/scripts/test_req_matrix.py"]) == 1


@pytest.mark.req("REQ-N-QA-06")
def test_req_matrix_cli_refuses_an_empty_catalog(tmp_path: Path) -> None:
    catalog = tmp_path / "empty.md"
    catalog.write_text("nothing here\n", encoding="utf-8")
    assert req_matrix.main(["--catalog", str(catalog)]) == 1


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "chore: initial\n\nRefs: DEC-023")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.req("REQ-N-QA-06")
def test_check_commits_cli_reads_real_git_history(repo: Path, tmp_path: Path) -> None:
    _git(repo, "commit", "-q", "--allow-empty", "-m", "feat(cards): add card entity\n\nRefs: REQ-F-CARD-07")
    body = tmp_path / "body.md"
    body.write_text("## Traceability\n\n- Requirements: REQ-F-CARD-07\n", encoding="utf-8")
    assert check_commits.main(["--range", "HEAD~1..HEAD", "--pr-body-file", str(body)]) == 0


@pytest.mark.req("REQ-N-QA-06")
def test_check_commits_cli_fails_on_a_bad_commit(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _git(repo, "commit", "-q", "--allow-empty", "-m", "Add stuff")
    assert check_commits.main(["--range", "HEAD~1..HEAD"]) == 1
    assert "not a Conventional Commit" in capsys.readouterr().err


@pytest.mark.req("REQ-N-QA-06")
def test_check_commits_cli_fails_on_an_empty_range(repo: Path) -> None:
    assert check_commits.main(["--range", "HEAD..HEAD"]) == 1

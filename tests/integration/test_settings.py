"""Django skeleton: production settings are deploy-safe and env-only; /healthz probes the DB.

ADR-002 §1 (config/ holds the Django project), DEC-039 (no secrets in the repo).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import Client
from pytest_django import DjangoAssertNumQueries

ROOT = Path(__file__).resolve().parents[2]

DUMMY_PRODUCTION_ENV = {
    "DJANGO_SETTINGS_MODULE": "config.settings.production",
    "DJANGO_SECRET_KEY": "dummy-check-deploy-value-0123456789-abcdefghijklmnopqrstuvwxyz",
    "DJANGO_ALLOWED_HOSTS": "api.example.com",
    "WEB_ORIGIN": "https://app.example.com",
    "DB_NAME": "cherrylove",
    "DB_USER": "app",
    "DB_PASSWORD": "dummy",
    "DB_MAINTENANCE_USER": "maintenance",
    "DB_MAINTENANCE_PASSWORD": "dummy",
    "DB_HOST": "db.invalid",
    "DB_PORT": "5432",
}


def _manage(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    clean = {k: v for k, v in os.environ.items() if k not in DUMMY_PRODUCTION_ENV}
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=ROOT,
        env={**clean, **env},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.req("REQ-N-ARC-01")
def test_production_settings_pass_check_deploy() -> None:
    result = _manage("check", "--deploy", "--fail-level", "WARNING", env=DUMMY_PRODUCTION_ENV)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.parametrize(
    "missing", ["DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "DB_PASSWORD", "DB_MAINTENANCE_PASSWORD"]
)
def test_production_settings_read_only_env_vars(missing: str) -> None:
    env = {k: v for k, v in DUMMY_PRODUCTION_ENV.items() if k != missing}
    result = _manage("check", env=env)
    assert result.returncode != 0
    assert f"Environment variable {missing} is required" in result.stderr


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.django_db
def test_healthz_returns_200_and_checks_the_database(
    client: Client, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    with django_assert_num_queries(1):
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.req("REQ-N-ARC-01")
def test_healthz_only_answers_get(client: Client) -> None:
    assert client.post("/healthz").status_code == 405

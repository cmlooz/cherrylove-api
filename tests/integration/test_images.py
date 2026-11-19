"""API and worker images start, answer /healthz and run as non-root (ADR-015 §3/§4).

Runs in the CI `images` job, which builds both images and exports their tags; skipped elsewhere.
"""

from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.integration

IMAGES = {
    "api": os.environ.get("CHERRYLOVE_API_IMAGE", ""),
    "worker": os.environ.get("CHERRYLOVE_WORKER_IMAGE", ""),
}
RUNTIME_ENV = {
    "DJANGO_SECRET_KEY": "ci-images-throwaway-0123456789-abcdefghijklmnopqrstuvwxyz",
    "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
    "WEB_ORIGIN": "http://localhost:5173",
    "AUDIT_HMAC_KEY": "ci-images-audit-hmac-throwaway",
    "DB_NAME": "cherrylove",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "5432",
    "DB_USER": "cherrylove_app",
    "DB_PASSWORD": os.environ.get("DB_PASSWORD", "local-app"),
    "DB_MAINTENANCE_USER": "cherrylove_maintenance",
    "DB_MAINTENANCE_PASSWORD": os.environ.get("DB_MAINTENANCE_PASSWORD", "local-maintenance"),
}
PORT = 8000  # the images' own CMD binds it; containers run one at a time on the host network


def _image(kind: str) -> str:
    image = IMAGES[kind]
    if not image:
        pytest.skip("set CHERRYLOVE_API_IMAGE / CHERRYLOVE_WORKER_IMAGE (CI images job)")
    return image


@pytest.fixture(params=sorted(IMAGES))
def container(request: pytest.FixtureRequest) -> Iterator[int]:
    kind: str = request.param
    image = _image(kind)
    name = f"cherrylove-{kind}-{uuid.uuid4().hex[:8]}"
    env_args = [arg for key, value in RUNTIME_ENV.items() for arg in ("-e", f"{key}={value}")]
    subprocess.run(
        ["docker", "run", "-d", "--name", name, "--network", "host", *env_args, image],
        check=True,
        capture_output=True,
    )
    yield PORT
    subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True)


def _get(url: str, attempts: int = 30) -> int:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                status: int = response.status
                return status
        except urllib.error.URLError, ConnectionError:
            time.sleep(1)
    return 0


@pytest.mark.req("REQ-N-QA-04")
def test_image_answers_healthz(container: int) -> None:
    assert _get(f"http://127.0.0.1:{container}/healthz") == 200


@pytest.mark.req("REQ-N-QA-04")
@pytest.mark.parametrize("kind", sorted(IMAGES))
def test_image_runs_as_non_root(kind: str) -> None:
    image = _image(kind)
    uid = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "id", image, "-u"], check=True, capture_output=True, text=True
    ).stdout.strip()
    assert uid == "10001"

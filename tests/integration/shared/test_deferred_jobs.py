"""The database task backend honours run_after with a real db_worker (IMPL-API-001 F1.16, ADR-013 §2).

ADR-013 relies on deferred execution for retries with backoff and says it is "verified in plan F". If this
test fails, stop: open an OQ and use the plan's fallback (`next_attempt_at` in shared_job_execution,
re-enqueued by the scheduler).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from django.db import connections

from cherrylove.shared.infrastructure.django_job_queue import DjangoJobQueue
from cherrylove.shared.infrastructure.orm import JobExecution

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[3]
DEFER = timedelta(seconds=5)


def _run_worker_batch() -> None:
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.test",
        "DB_NAME": str(connections["default"].settings_dict["NAME"]),
    }
    subprocess.run(
        [sys.executable, "manage.py", "db_worker", "--batch", "--no-startup-delay", "--queue-name", "default"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        timeout=60,
    )


def _succeeded(key: str) -> bool:
    return JobExecution.objects.filter(idempotency_key=key, status="succeeded").exists()


@pytest.mark.req("REQ-N-ARC-01")
@pytest.mark.django_db(transaction=True)
def test_a_deferred_job_waits_for_run_after_then_runs() -> None:
    queue = DjangoJobQueue()
    now_key, later_key = f"test:now:{uuid.uuid4().hex}", f"test:later:{uuid.uuid4().hex}"
    run_after = datetime.now(tz=UTC) + DEFER
    queue.enqueue("test.probe.noop", {}, idempotency_key=now_key)
    queue.enqueue("test.probe.noop", {}, idempotency_key=later_key, run_after=run_after)

    _run_worker_batch()
    assert _succeeded(now_key), "control: an immediate job runs in the first batch"
    assert not _succeeded(later_key), "a job with run_after in the future must not be picked yet"

    time.sleep(max(0.0, (run_after - datetime.now(tz=UTC)).total_seconds()) + 0.5)
    _run_worker_batch()
    assert _succeeded(later_key)

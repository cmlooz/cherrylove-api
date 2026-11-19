"""Probe jobs for worker-level tests (F1.16): they only need to be registered in the worker process."""

from __future__ import annotations

from cherrylove.shared.application.job_queue import Payload
from cherrylove.shared.infrastructure.django_job_queue import register_job


@register_job("test.probe.noop")
def noop(payload: Payload) -> None:
    return None

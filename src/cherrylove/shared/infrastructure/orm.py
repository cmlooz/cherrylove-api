"""Shared kernel tables (DATA-001 §5)."""

from __future__ import annotations

from django.db import models


class JobExecution(models.Model):
    """One row per idempotency key (ADR-013 §2): a second run with the same key is a no-op."""

    class Status(models.TextChoices):
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    idempotency_key = models.CharField(max_length=255, unique=True)
    job = models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=Status.choices)
    attempts = models.PositiveIntegerField(default=0)
    last_error_code = models.CharField(max_length=100, null=True, blank=True)  # noqa: DJ001 - null = no error yet
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "shared"
        db_table = "shared_job_execution"

    def __str__(self) -> str:
        return f"{self.idempotency_key} ({self.status})"

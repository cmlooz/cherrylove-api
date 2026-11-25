"""Shared kernel tables (DATA-001 §5)."""

from __future__ import annotations

from typing import ClassVar

from django.db import models


class JobExecution(models.Model):
    """One row per idempotency key (ADR-013 §2): a second run with the same key is a no-op."""

    class Status(models.TextChoices):
        RUNNING = "running"
        RETRYING = "retrying"
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


class CoupleDataKey(models.Model):
    """One wrapped DEK per couple and key_id (ADR-009 §1): never the plaintext key."""

    pk = models.CompositePrimaryKey("couple_id", "key_id")
    # Lazy reference: the kernel never imports the identity module (ADR-001 §1).
    couple = models.ForeignKey("identity.Couple", on_delete=models.PROTECT, related_name="+")
    key_id = models.PositiveIntegerField()
    wrapped_dek = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "shared"
        db_table = "shared_couple_data_key"
        constraints: ClassVar = [models.CheckConstraint(condition=models.Q(key_id__gte=1), name="shared_dek_key_id")]

    def __str__(self) -> str:
        return f"{self.couple_id}#{self.key_id}"

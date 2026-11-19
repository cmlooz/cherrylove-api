"""Test-only couple-owned model for the fail-closed manager (installed by config.settings.test only)."""

from __future__ import annotations

from django.db import models

from cherrylove.shared.infrastructure.scoping import CoupleScopedManager


class ScopedProbe(models.Model):
    couple_id = models.UUIDField()
    note = models.TextField()

    objects = CoupleScopedManager["ScopedProbe"]()
    unscoped = models.Manager["ScopedProbe"]()

    class Meta:
        app_label = "scoping"
        base_manager_name = "unscoped"

    def __str__(self) -> str:
        return self.note


class ProbeChange(models.Model):
    """Stands in for sync_entity_index until the ChangeRecorder adapter lands (F2.3)."""

    couple_id = models.UUIDField()
    entity_type = models.CharField(max_length=20)
    entity_id = models.UUIDField()
    author_id = models.UUIDField(null=True)

    class Meta:
        app_label = "scoping"

    def __str__(self) -> str:
        return f"{self.entity_type}:{self.entity_id}"

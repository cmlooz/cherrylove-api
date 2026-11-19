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

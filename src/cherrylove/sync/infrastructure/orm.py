"""Sync server data (ADR-006 §1, DATA-001): one counter per couple and one index row per entity."""

from __future__ import annotations

from typing import ClassVar

from django.db import models

# Foreign keys to Couple are allowed (ADR-001 §3, REQ-N-ARC-05); a lazy reference keeps modules decoupled.
COUPLE = "identity.Couple"

ENTITY_TYPES = ["card", "memory", "song", "place", "note", "favorite", "couple", "media_asset"]


class SyncState(models.Model):
    couple = models.OneToOneField(COUPLE, on_delete=models.PROTECT, primary_key=True, related_name="sync_state")
    last_seq = models.BigIntegerField(default=0)
    purged_through_seq = models.BigIntegerField(default=0)

    class Meta:
        app_label = "sync"
        db_table = "sync_state"

    def __str__(self) -> str:
        return f"{self.couple_id}@{self.last_seq}"


class SyncEntityIndex(models.Model):
    """Upserted on every change: the latest seq of each entity, not a growing log (ADR-006 §1)."""

    couple = models.ForeignKey(COUPLE, on_delete=models.PROTECT, related_name="+")
    entity_type = models.CharField(max_length=20)
    entity_id = models.UUIDField()
    seq = models.BigIntegerField()
    author_id = models.UUIDField(null=True)

    class Meta:
        app_label = "sync"
        db_table = "sync_entity_index"
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["couple", "entity_type", "entity_id"], name="sync_entity_index_uniq"),
            models.CheckConstraint(condition=models.Q(entity_type__in=ENTITY_TYPES), name="sync_entity_type"),
        ]
        indexes: ClassVar = [models.Index(fields=["couple", "seq"], name="sync_entity_index_seq_idx")]

    def __str__(self) -> str:
        return f"{self.entity_type}:{self.entity_id}@{self.seq}"

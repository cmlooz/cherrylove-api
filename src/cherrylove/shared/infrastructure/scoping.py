"""Fail-closed ORM access for couple-owned models (ADR-005 §3, REQ-N-SEC-01).

    class Memory(models.Model):
        objects = CoupleScopedManager()   # default: every query raises unless scoped
        unscoped = models.Manager()       # backoffice metadata and migrations only (architecture test)

Reads go through `Memory.objects.for_couple(couple_id)`. Writes use instances (`save()` goes through the base
manager), so a repository never needs the unscoped manager.
"""

from __future__ import annotations

from typing import Any

from django.db import models

from cherrylove.shared.domain.ids import CoupleId


class UnscopedQueryError(RuntimeError):
    """A couple-owned model was queried without `for_couple(couple_id)`."""


class CoupleScopedManager[M: models.Model](models.Manager[M]):
    def get_queryset(self) -> models.QuerySet[M]:
        model = self.model.__name__
        raise UnscopedQueryError(f"{model}.objects needs .for_couple(couple_id) (ADR-005 §3)")

    def for_couple(self, couple_id: CoupleId) -> models.QuerySet[M]:
        if not isinstance(couple_id, CoupleId):
            raise TypeError(f"for_couple() needs a CoupleId, got {type(couple_id).__name__}")
        return super().get_queryset().filter(couple_id=couple_id.value)

    def create(self, **kwargs: Any) -> M:
        raise UnscopedQueryError("create through a repository: build the instance and call save()")

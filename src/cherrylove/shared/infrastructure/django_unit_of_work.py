"""Django adapter of the UnitOfWork port (ADR-001 §5): `transaction.atomic` on the app connection."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager

from django.db import transaction


class DjangoUnitOfWork:
    def __init__(self, using: str = "default") -> None:
        self.using = using

    def atomic(self) -> AbstractContextManager[None]:
        return transaction.atomic(using=self.using)

    def on_commit(self, callback: Callable[[], None]) -> None:
        # robust: a failing after-commit callback is logged and never undoes the committed work (ADR-001 §4).
        transaction.on_commit(callback, using=self.using, robust=True)

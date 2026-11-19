"""Unit of Work port (ADR-001 §5): a use case owns its transaction; repositories never open one."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol


class UnitOfWork(Protocol):
    def atomic(self) -> AbstractContextManager[None]:
        """Everything inside commits together or not at all; nested blocks are savepoints."""
        ...

    def on_commit(self, callback: Callable[[], None]) -> None:
        """Run `callback` after the outermost block commits; drop it if the block it belongs to rolls back."""
        ...

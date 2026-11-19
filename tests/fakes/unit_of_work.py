"""In-memory UnitOfWork with Django's semantics: savepoints, after-commit callbacks, robust dispatch."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

logger = logging.getLogger(__name__)


class InMemoryUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self._pending: list[list[Callable[[], None]]] = []

    @contextmanager
    def _block(self) -> Iterator[None]:
        self._pending.append([])
        try:
            yield
        except BaseException:
            self._pending.pop()
            self.rollbacks += 1
            raise
        callbacks = self._pending.pop()
        if self._pending:
            self._pending[-1].extend(callbacks)
            return
        self.commits += 1
        for callback in callbacks:
            self._run(callback)

    def atomic(self) -> AbstractContextManager[None]:
        return self._block()

    def on_commit(self, callback: Callable[[], None]) -> None:
        if self._pending:
            self._pending[-1].append(callback)
        else:
            self._run(callback)

    @staticmethod
    def _run(callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:
            logger.exception("after-commit callback failed")

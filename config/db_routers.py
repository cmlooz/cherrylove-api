"""Database routing: schema changes only through the maintenance role (ADR-008 §4).

While `migrate --database maintenance` runs, every ORM read and write is routed to the maintenance connection
too. Third-party data migrations that forget `.using(schema_editor.connection.alias)` (django-tasks-db 0.13.0,
migration 0016) would otherwise write through the app connection and wait forever for a lock held by the
maintenance connection's own migration transaction.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

MAINTENANCE = "maintenance"

_migrating: ContextVar[bool] = ContextVar("migrating_as_maintenance", default=False)


def start_maintenance_migration(sender: Any = None, using: str = "", **kwargs: Any) -> None:
    """`pre_migrate` receiver."""
    if using == MAINTENANCE:
        _migrating.set(True)


def end_maintenance_migration(sender: Any = None, using: str = "", **kwargs: Any) -> None:
    """`post_migrate` receiver."""
    if using == MAINTENANCE:
        _migrating.set(False)


class MaintenanceMigrationsRouter:
    def allow_migrate(self, db: str, app_label: str, **hints: Any) -> bool:
        return db == MAINTENANCE

    def db_for_read(self, model: type[Any], **hints: Any) -> str | None:
        return MAINTENANCE if _migrating.get() else None

    def db_for_write(self, model: type[Any], **hints: Any) -> str | None:
        return MAINTENANCE if _migrating.get() else None

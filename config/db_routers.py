"""Database routing: schema changes only through the maintenance role (ADR-008 §4)."""

from __future__ import annotations

from typing import Any

MAINTENANCE = "maintenance"


class MaintenanceMigrationsRouter:
    def allow_migrate(self, db: str, app_label: str, **hints: Any) -> bool:
        return db == MAINTENANCE

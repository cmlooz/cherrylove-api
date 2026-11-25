"""Migrations route every ORM query to the maintenance connection (F1.15 fix, ADR-008 §4).

django-tasks-db 0.13.0 migration 0016 writes without `.using(...)`; without this routing it waits forever
for a lock held by the maintenance connection's own migration transaction.
"""

from __future__ import annotations

import pytest
from django.db.models.signals import post_migrate, pre_migrate

from cherrylove.shared.infrastructure.orm import JobExecution
from config.db_routers import MaintenanceMigrationsRouter, end_maintenance_migration, start_maintenance_migration

ROUTER = MaintenanceMigrationsRouter()


@pytest.mark.req("REQ-F-LOG-03")
def test_outside_migrations_the_app_connection_is_used() -> None:
    assert ROUTER.db_for_read(JobExecution) is None
    assert ROUTER.db_for_write(JobExecution) is None


@pytest.mark.req("REQ-F-LOG-03")
def test_during_maintenance_migrations_every_query_uses_maintenance() -> None:
    start_maintenance_migration(using="maintenance")
    try:
        assert ROUTER.db_for_read(JobExecution) == "maintenance"
        assert ROUTER.db_for_write(JobExecution) == "maintenance"
    finally:
        end_maintenance_migration(using="maintenance")
    assert ROUTER.db_for_write(JobExecution) is None


@pytest.mark.req("REQ-F-LOG-03")
def test_the_receivers_are_connected_to_the_migrate_signals() -> None:
    def uids(signal: object) -> set[object]:
        return {key[0] for key, *_ in signal.receivers}  # type: ignore[attr-defined]

    assert "cherrylove.start_maintenance_migration" in uids(pre_migrate)
    assert "cherrylove.end_maintenance_migration" in uids(post_migrate)


@pytest.mark.req("REQ-F-LOG-03")
def test_signals_for_other_aliases_change_nothing() -> None:
    start_maintenance_migration(using="default")
    assert ROUTER.db_for_write(JobExecution) is None


@pytest.mark.req("REQ-F-LOG-03")
def test_only_the_maintenance_alias_migrates() -> None:
    assert ROUTER.allow_migrate("maintenance", "shared") is True
    assert ROUTER.allow_migrate("default", "shared") is False

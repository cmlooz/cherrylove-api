"""Migrations route every ORM query to the maintenance connection (F1.15 fix, ADR-008 §4).

django-tasks-db 0.13.0 migration 0016 writes without `.using(...)`; without this routing it waits forever
for a lock held by the maintenance connection's own migration transaction.
"""

from __future__ import annotations

import pytest
from django.db.models.signals import post_migrate, pre_migrate

from cherrylove.shared.infrastructure.orm import JobExecution
from config.db_routers import MaintenanceMigrationsRouter

ROUTER = MaintenanceMigrationsRouter()


@pytest.mark.req("REQ-F-LOG-03")
def test_outside_migrations_the_app_connection_is_used() -> None:
    assert ROUTER.db_for_read(JobExecution) is None
    assert ROUTER.db_for_write(JobExecution) is None


@pytest.mark.req("REQ-F-LOG-03")
def test_during_maintenance_migrations_every_query_uses_maintenance() -> None:
    pre_migrate.send(sender=None, app_config=None, using="maintenance")
    try:
        assert ROUTER.db_for_read(JobExecution) == "maintenance"
        assert ROUTER.db_for_write(JobExecution) == "maintenance"
    finally:
        post_migrate.send(sender=None, app_config=None, using="maintenance")
    assert ROUTER.db_for_write(JobExecution) is None


@pytest.mark.req("REQ-F-LOG-03")
def test_signals_for_other_aliases_change_nothing() -> None:
    pre_migrate.send(sender=None, app_config=None, using="default")
    assert ROUTER.db_for_write(JobExecution) is None


@pytest.mark.req("REQ-F-LOG-03")
def test_only_the_maintenance_alias_migrates() -> None:
    assert ROUTER.allow_migrate("maintenance", "shared") is True
    assert ROUTER.allow_migrate("default", "shared") is False

"""Every table is created after the app-role default privileges (ADR-008 §4, DATA-001 §3).

Django creates tables of apps without migrations (syncdb) before running migrations, and a migration that
does not depend on shared.0001 may run before it: either way the table misses the app role DML grants.
"""

from __future__ import annotations

import pytest
from django.apps import apps
from django.db.migrations.loader import MigrationLoader

ROOT = ("shared", "0001_app_role_default_privileges")


THIRD_PARTY = ("django.", "rest_framework", "drf_spectacular")


@pytest.mark.req("REQ-F-LOG-03")
def test_every_app_with_models_has_migrations() -> None:
    loader = MigrationLoader(None, ignore_no_migrations=True)
    unmigrated = sorted(
        config.label
        for config in apps.get_app_configs()
        if not config.name.startswith(THIRD_PARTY) and list(config.get_models())
        if config.label not in loader.migrated_apps
    )
    assert unmigrated == []


@pytest.mark.req("REQ-F-LOG-03")
def test_every_initial_migration_runs_after_the_default_privileges() -> None:
    loader = MigrationLoader(None, ignore_no_migrations=True)
    graph = loader.graph
    for app_label, name in graph.leaf_nodes():
        if app_label not in {config.label for config in apps.get_app_configs()} or (app_label, name) == ROOT:
            continue
        if apps.get_app_config(app_label).name.startswith(THIRD_PARTY):
            continue
        initial = graph.root_nodes(app_label)[0]
        if initial == ROOT:
            continue
        assert ROOT in graph.forwards_plan(initial), f"{app_label}.{initial[1]} must depend on shared.0001"

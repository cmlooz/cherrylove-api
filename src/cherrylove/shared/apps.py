from __future__ import annotations

from django.apps import AppConfig


class SharedConfig(AppConfig):
    name = "cherrylove.shared"
    label = "shared"

    def ready(self) -> None:
        from django.db.models.signals import post_migrate, pre_migrate  # noqa: PLC0415

        from cherrylove.shared.infrastructure import checks  # noqa: F401, PLC0415 - registers startup checks
        from config.db_routers import end_maintenance_migration, start_maintenance_migration  # noqa: PLC0415

        pre_migrate.connect(start_maintenance_migration, dispatch_uid="cherrylove.start_maintenance_migration")
        post_migrate.connect(end_maintenance_migration, dispatch_uid="cherrylove.end_maintenance_migration")

"""Test-only app (config.settings.test): probe model and probe jobs visible to a real worker process."""

from __future__ import annotations

from django.apps import AppConfig


class ScopingConfig(AppConfig):
    name = "tests.apps.scoping"
    label = "scoping"

    def ready(self) -> None:
        from tests.apps.scoping import jobs  # noqa: F401, PLC0415 - registers the probe jobs

from __future__ import annotations

from django.apps import AppConfig


class SharedConfig(AppConfig):
    name = "cherrylove.shared"
    label = "shared"

    def ready(self) -> None:
        from cherrylove.shared.infrastructure import checks  # noqa: F401, PLC0415 - registers startup checks

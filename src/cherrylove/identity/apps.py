from __future__ import annotations

from django.apps import AppConfig


class IdentityConfig(AppConfig):
    name = "cherrylove.identity"
    label = "identity"

    def ready(self) -> None:
        from cherrylove.identity.interfaces import jobs  # noqa: F401, PLC0415 - registers job handlers
        from cherrylove.identity.interfaces.http import authentication  # noqa: F401, PLC0415 - OpenAPI scheme

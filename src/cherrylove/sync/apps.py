from __future__ import annotations

from django.apps import AppConfig


class SyncConfig(AppConfig):
    name = "cherrylove.sync"
    label = "sync"

    def ready(self) -> None:
        # Composition root: other modules reach sync only through application.public (ADR-001 §3).
        from cherrylove.sync.application.public import register_sync_state_provisioner  # noqa: PLC0415
        from cherrylove.sync.infrastructure.provisioning import DjangoSyncStateProvisioner  # noqa: PLC0415

        register_sync_state_provisioner(DjangoSyncStateProvisioner())

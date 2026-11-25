"""Sync facade for other modules (ADR-001 §3): the only door into `sync`.

The sync app registers its adapters at startup (`SyncConfig.ready`), so callers never import sync
infrastructure and this layer never imports it either.
"""

from __future__ import annotations

from typing import Protocol

from cherrylove.shared.domain.ids import CoupleId


class SyncStateProvisioner(Protocol):
    def provision(self, couple_id: CoupleId) -> None: ...


_provisioner: SyncStateProvisioner | None = None


def register_sync_state_provisioner(provisioner: SyncStateProvisioner) -> None:
    global _provisioner  # noqa: PLW0603 - composition-root hook, set once at startup
    _provisioner = provisioner


def provision_sync_state(couple_id: CoupleId) -> None:
    """Create the couple's sync_state row (seq 0); call it inside the create-couple transaction (F2.5)."""
    if _provisioner is None:
        raise RuntimeError("the sync app is not ready: no SyncStateProvisioner registered")
    _provisioner.provision(couple_id)

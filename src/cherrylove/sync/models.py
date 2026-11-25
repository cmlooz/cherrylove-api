"""Django discovery shim (ADR-002 §1)."""

from __future__ import annotations

from cherrylove.sync.infrastructure.orm import SyncEntityIndex, SyncState

__all__ = ["SyncEntityIndex", "SyncState"]

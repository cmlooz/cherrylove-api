"""Creates sync_state with the couple (ADR-006 §1)."""

from __future__ import annotations

from cherrylove.shared.domain.ids import CoupleId
from cherrylove.sync.infrastructure.orm import SyncState


class DjangoSyncStateProvisioner:
    def provision(self, couple_id: CoupleId) -> None:
        SyncState(couple_id=couple_id.value).save(force_insert=True)

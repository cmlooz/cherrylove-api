"""What other modules create together with a couple: sync_state (via the sync facade) and the data key."""

from __future__ import annotations

from django.conf import settings

from cherrylove.shared.domain.ids import CoupleId
from cherrylove.shared.infrastructure.crypto.aes_gcm import Kek
from cherrylove.shared.infrastructure.crypto.dek_store import DjangoDekStore, provision_couple_key
from cherrylove.sync.application.public import provision_sync_state


class SyncStateViaFacade:
    def provision(self, couple_id: CoupleId) -> None:
        provision_sync_state(couple_id)


class CoupleDataKeyProvisioner:
    def provision(self, couple_id: CoupleId) -> None:
        provision_couple_key(DjangoDekStore(), Kek.from_base64(settings.KEK), couple_id)

"""DekStore adapter on shared_couple_data_key (ADR-009 §1, §6; DATA-001 §5)."""

from __future__ import annotations

from cherrylove.shared.application.cipher import WrappedDek
from cherrylove.shared.domain.errors import NotFound
from cherrylove.shared.domain.ids import CoupleId
from cherrylove.shared.infrastructure.crypto.aes_gcm import Kek, new_dek
from cherrylove.shared.infrastructure.orm import CoupleDataKey

FIRST_KEY_ID = 1


class DjangoDekStore:
    def current(self, couple_id: CoupleId) -> WrappedDek:
        row = CoupleDataKey.objects.filter(couple_id=couple_id.value).order_by("-key_id").first()
        if row is None:
            raise NotFound("the couple has no data key")
        return WrappedDek(row.key_id, bytes(row.wrapped_dek))

    def get(self, couple_id: CoupleId, key_id: int) -> WrappedDek | None:
        row = CoupleDataKey.objects.filter(couple_id=couple_id.value, key_id=key_id).first()
        return WrappedDek(row.key_id, bytes(row.wrapped_dek)) if row else None

    def save(self, couple_id: CoupleId, dek: WrappedDek) -> None:
        CoupleDataKey.objects.update_or_create(
            couple_id=couple_id.value, key_id=dek.key_id, defaults={"wrapped_dek": dek.wrapped}
        )


def provision_couple_key(store: DjangoDekStore, kek: Kek, couple_id: CoupleId) -> None:
    """Create the couple's first DEK, stored only wrapped (called inside the create-couple transaction)."""
    store.save(couple_id, kek.wrap(couple_id, FIRST_KEY_ID, new_dek()))

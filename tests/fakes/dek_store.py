"""In-memory DekStore (ADR-009 §1); the `shared_couple_data_key` table adapter lands in F2.4."""

from __future__ import annotations

from dataclasses import dataclass, field

from cherrylove.shared.application.cipher import WrappedDek
from cherrylove.shared.domain.errors import NotFound
from cherrylove.shared.domain.ids import CoupleId


@dataclass
class InMemoryDekStore:
    keys: dict[tuple[CoupleId, int], WrappedDek] = field(default_factory=dict)
    reads: int = 0

    def current(self, couple_id: CoupleId) -> WrappedDek:
        ids = [key_id for (owner, key_id) in self.keys if owner == couple_id]
        if not ids:
            raise NotFound("no data key")
        self.reads += 1
        return self.keys[(couple_id, max(ids))]

    def get(self, couple_id: CoupleId, key_id: int) -> WrappedDek | None:
        self.reads += 1
        return self.keys.get((couple_id, key_id))

    def save(self, couple_id: CoupleId, dek: WrappedDek) -> None:
        self.keys[(couple_id, dek.key_id)] = dek

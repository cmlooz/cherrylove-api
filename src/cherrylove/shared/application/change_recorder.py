"""ChangeRecorder port (ADR-006 §1): every syncable write records a change **inside** its unit of work.

The adapter (sync, F2.3) bumps `sync_state.last_seq` and upserts `sync_entity_index`. No after-commit event
is used: a lost event would be a missed change.
"""

from __future__ import annotations

import uuid
from typing import Literal, Protocol

from cherrylove.shared.domain.ids import CoupleId, UserId

# Contract `SyncEntityType` (API-001, DEC-050).
type EntityType = Literal["card", "memory", "song", "place", "note", "favorite", "couple", "media_asset"]


class ChangeRecorder(Protocol):
    def record(
        self, couple_id: CoupleId, entity_type: EntityType, entity_id: uuid.UUID, author_id: UserId | None
    ) -> None:
        """`author_id` is None for changes made by the system (e.g. the card publish job, ADR-006 §1)."""
        ...

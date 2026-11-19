"""In-memory ChangeRecorder: records changes in call order (ADR-006 §1)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from cherrylove.shared.application.change_recorder import EntityType
from cherrylove.shared.domain.ids import CoupleId, UserId


@dataclass(frozen=True)
class RecordedChange:
    couple_id: CoupleId
    entity_type: EntityType
    entity_id: uuid.UUID
    author_id: UserId | None


@dataclass
class InMemoryChangeRecorder:
    changes: list[RecordedChange] = field(default_factory=list)

    def record(
        self, couple_id: CoupleId, entity_type: EntityType, entity_id: uuid.UUID, author_id: UserId | None
    ) -> None:
        self.changes.append(RecordedChange(couple_id, entity_type, entity_id, author_id))

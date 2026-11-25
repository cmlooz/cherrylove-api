"""ChangeRecorder adapter on sync_state (ADR-006 §1, REQ-F-SYNC-06).

`UPDATE sync_state ... RETURNING last_seq` takes the couple's row lock until the use-case transaction ends,
so concurrent writers of one couple get consecutive seq values and commit in seq order: a pull cursor never
skips a change that commits later with a smaller seq.
"""

from __future__ import annotations

import uuid

from django.db import connections

from cherrylove.shared.application.change_recorder import EntityType
from cherrylove.shared.domain.ids import CoupleId, UserId

NEXT_SEQ = "UPDATE sync_state SET last_seq = last_seq + 1 WHERE couple_id = %s RETURNING last_seq"
UPSERT_INDEX = """
INSERT INTO sync_entity_index (couple_id, entity_type, entity_id, seq, author_id)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (couple_id, entity_type, entity_id) DO UPDATE SET seq = EXCLUDED.seq, author_id = EXCLUDED.author_id
"""


class MissingSyncStateError(LookupError):
    """The couple has no sync_state row: it must be created with the couple (F2.5)."""


class PostgresChangeRecorder:
    def __init__(self, using: str = "default") -> None:
        self._using = using

    def record(
        self, couple_id: CoupleId, entity_type: EntityType, entity_id: uuid.UUID, author_id: UserId | None
    ) -> None:
        with connections[self._using].cursor() as cursor:
            cursor.execute(NEXT_SEQ, [couple_id.value])
            row = cursor.fetchone()
            if row is None:
                raise MissingSyncStateError(str(couple_id))
            cursor.execute(
                UPSERT_INDEX, [couple_id.value, entity_type, entity_id, row[0], author_id.value if author_id else None]
            )

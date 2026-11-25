"""ChangeRecorder on sync_state (IMPL-API-001 F2.3; ADR-006 §1, REQ-F-SYNC-06)."""

from __future__ import annotations

import threading
import uuid

import pytest
from django.db import connection

from cherrylove.identity.infrastructure.orm import Couple
from cherrylove.shared.application.change_recorder import ChangeRecorder
from cherrylove.shared.domain.ids import CoupleId, UserId
from cherrylove.shared.infrastructure.django_unit_of_work import DjangoUnitOfWork
from cherrylove.sync.infrastructure.change_recorder import MissingSyncStateError, PostgresChangeRecorder
from cherrylove.sync.infrastructure.orm import SyncEntityIndex, SyncState

pytestmark = pytest.mark.integration


def _couple() -> CoupleId:
    couple = Couple.objects.create()
    SyncState.objects.create(couple=couple)
    return CoupleId(couple.id)


@pytest.mark.req("REQ-F-SYNC-06")
@pytest.mark.django_db
def test_each_change_bumps_seq_and_upserts_one_index_row_per_entity() -> None:
    recorder: ChangeRecorder = PostgresChangeRecorder()
    couple, author, card = _couple(), UserId(uuid.uuid7()), uuid.uuid7()
    recorder.record(couple, "card", card, author)
    recorder.record(couple, "note", uuid.uuid7(), None)
    recorder.record(couple, "card", card, author)
    assert SyncState.objects.get(couple_id=couple.value).last_seq == 3
    row = SyncEntityIndex.objects.get(couple_id=couple.value, entity_type="card", entity_id=card)
    assert (row.seq, row.author_id) == (3, author.value)
    assert SyncEntityIndex.objects.filter(couple_id=couple.value).count() == 2


@pytest.mark.req("REQ-F-SYNC-06")
@pytest.mark.django_db
def test_a_couple_without_sync_state_is_a_programming_error() -> None:
    with pytest.raises(MissingSyncStateError):
        PostgresChangeRecorder().record(CoupleId(Couple.objects.create().id), "card", uuid.uuid7(), None)


@pytest.mark.req("REQ-F-SYNC-06")
@pytest.mark.django_db(transaction=True)
def test_concurrent_writers_get_consecutive_seq_in_commit_order() -> None:
    couple = _couple()
    first_holds_lock, release_first = threading.Event(), threading.Event()
    seen: dict[str, int] = {}

    def writer(name: str, entity: uuid.UUID, hold: bool) -> None:
        try:
            with DjangoUnitOfWork().atomic():
                PostgresChangeRecorder().record(couple, "note", entity, None)
                seen[name] = SyncEntityIndex.objects.get(entity_id=entity).seq
                if hold:
                    first_holds_lock.set()
                    release_first.wait(timeout=10)
            seen[f"{name}_committed_at"] = len(seen)
        finally:
            connection.close()

    a = threading.Thread(target=writer, args=("a", uuid.uuid7(), True))
    a.start()
    assert first_holds_lock.wait(timeout=10)
    b = threading.Thread(target=writer, args=("b", uuid.uuid7(), False))
    b.start()
    b.join(timeout=1)
    assert b.is_alive(), "the second writer must wait for the couple's row lock"
    release_first.set()
    a.join(timeout=10)
    b.join(timeout=10)

    assert (seen["a"], seen["b"]) == (1, 2)
    assert seen["a_committed_at"] < seen["b_committed_at"]
    assert SyncState.objects.get(couple_id=couple.value).last_seq == 2

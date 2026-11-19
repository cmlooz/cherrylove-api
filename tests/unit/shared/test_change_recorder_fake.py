"""The in-memory ChangeRecorder fake (IMPL-API-001 F1.5, ADR-006 §1); the adapter lands in F2.3."""

from __future__ import annotations

import pytest

from cherrylove.shared.application.change_recorder import ChangeRecorder
from cherrylove.shared.domain.ids import CoupleId, UserId
from tests.fakes.change_recorder import InMemoryChangeRecorder, RecordedChange
from tests.fakes.clock import FixedClock, SequentialIdGenerator


@pytest.mark.req("REQ-F-SYNC-06")
def test_records_couple_type_id_and_author_in_call_order() -> None:
    ids = SequentialIdGenerator(FixedClock())
    couple, author = CoupleId(ids.new()), UserId(ids.new())
    card, note = ids.new(), ids.new()
    fake = InMemoryChangeRecorder()
    recorder: ChangeRecorder = fake
    recorder.record(couple, "card", card, author)
    recorder.record(couple, "note", note, None)
    recorder.record(couple, "card", card, author)
    assert fake.changes == [
        RecordedChange(couple, "card", card, author),
        RecordedChange(couple, "note", note, None),
        RecordedChange(couple, "card", card, author),
    ]

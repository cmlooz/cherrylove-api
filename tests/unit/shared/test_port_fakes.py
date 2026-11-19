"""Every shared port has an in-memory fake that honours the port's contract (IMPL-API-001 F1 done criteria)."""

from __future__ import annotations

import pytest

from cherrylove.shared.application.audit_log import AuditEvent, AuditLog
from cherrylove.shared.application.cipher import Cipher, DecryptionError, FieldLocation
from cherrylove.shared.domain.ids import CoupleId
from tests.fakes.audit_log import InMemoryAuditLog
from tests.fakes.cipher import FakeCipher
from tests.fakes.clock import FixedClock, SequentialIdGenerator

IDS = SequentialIdGenerator(FixedClock())
COUPLE = CoupleId(IDS.new())
WHERE = FieldLocation("note", IDS.new(), "body")


@pytest.mark.req("REQ-F-LOG-01")
def test_audit_fake_keeps_in_transaction_and_rejected_events_apart() -> None:
    fake = InMemoryAuditLog()
    port: AuditLog = fake
    port.record(AuditEvent(action="note.created"))
    port.record_rejected(AuditEvent(action="note.created", outcome="rejected"))
    assert [e.outcome for e in fake.events] == ["success"]
    assert [e.outcome for e in fake.rejected] == ["rejected"]


@pytest.mark.req("REQ-N-SEC-05")
def test_cipher_fake_round_trips_and_refuses_another_place() -> None:
    cipher: Cipher = FakeCipher()
    blob = cipher.encrypt(COUPLE, WHERE, "dear diary")
    assert cipher.decrypt(COUPLE, WHERE, blob) == "dear diary"
    with pytest.raises(DecryptionError):
        cipher.decrypt(COUPLE, FieldLocation("note", IDS.new(), "body"), blob)
    with pytest.raises(DecryptionError):
        cipher.decrypt(COUPLE, WHERE, b"no separator")

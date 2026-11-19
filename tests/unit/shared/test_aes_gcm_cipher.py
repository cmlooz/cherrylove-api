"""AES-GCM envelope cipher (IMPL-API-001 F1.13; ADR-009 §1-3, §6; REQ-N-SEC-05)."""

from __future__ import annotations

import base64
import os
import uuid
from datetime import timedelta

import pytest
from django.test import override_settings
from hypothesis import given
from hypothesis import strategies as st

from cherrylove.shared.application.cipher import Cipher, DecryptionError, FieldLocation
from cherrylove.shared.domain.ids import CoupleId
from cherrylove.shared.infrastructure.checks import kek_is_256_bits
from cherrylove.shared.infrastructure.crypto.aes_gcm import AesGcmCipher, Kek, new_dek, rewrap
from tests.fakes.clock import FixedClock, SequentialIdGenerator
from tests.fakes.dek_store import InMemoryDekStore

IDS = SequentialIdGenerator(FixedClock())
COUPLE = CoupleId(IDS.new())
OTHER_COUPLE = CoupleId(IDS.new())
CARD = FieldLocation("card", IDS.new(), "body")


def _setup(*couples: CoupleId) -> tuple[AesGcmCipher, InMemoryDekStore, Kek, FixedClock]:
    kek, store, clock = Kek(os.urandom(32)), InMemoryDekStore(), FixedClock()
    for couple in couples or (COUPLE,):
        store.save(couple, kek.wrap(couple, 1, new_dek()))
    return AesGcmCipher(store, kek, clock), store, kek, clock


@pytest.mark.req("REQ-N-SEC-05")
@given(plaintext=st.text(max_size=2000))
def test_round_trip(plaintext: str) -> None:
    cipher: Cipher = _setup()[0]
    assert cipher.decrypt(COUPLE, CARD, cipher.encrypt(COUPLE, CARD, plaintext)) == plaintext


@pytest.mark.req("REQ-N-SEC-05")
def test_format_is_version_key_id_nonce_ciphertext() -> None:
    cipher = _setup()[0]
    blob = cipher.encrypt(COUPLE, CARD, "Te amo")
    assert blob[0] == 1
    assert int.from_bytes(blob[1:5], "big") == 1
    assert len(blob) == 1 + 4 + 12 + len(b"Te amo") + 16
    assert b"Te amo" not in blob


@pytest.mark.req("REQ-N-SEC-05")
def test_same_plaintext_never_gives_the_same_bytes() -> None:
    cipher = _setup()[0]
    assert cipher.encrypt(COUPLE, CARD, "x") != cipher.encrypt(COUPLE, CARD, "x")


@pytest.mark.req("REQ-N-SEC-05")
@pytest.mark.parametrize(
    ("couple", "where"),
    [
        (COUPLE, FieldLocation("card", uuid.uuid7(), "body")),
        (COUPLE, FieldLocation("card", CARD.entity_id, "title")),
        (COUPLE, FieldLocation("note", CARD.entity_id, "body")),
        (OTHER_COUPLE, CARD),
    ],
    ids=["other-row", "other-field", "other-entity-type", "other-couple"],
)
def test_aad_swap_fails(couple: CoupleId, where: FieldLocation) -> None:
    cipher = _setup(COUPLE, OTHER_COUPLE)[0]
    blob = cipher.encrypt(COUPLE, CARD, "secret")
    with pytest.raises(DecryptionError):
        cipher.decrypt(couple, where, blob)


@pytest.mark.req("REQ-N-SEC-05")
@pytest.mark.parametrize("index", [0, 3, 10, 20, -1])
def test_tampered_byte_fails(index: int) -> None:
    cipher = _setup()[0]
    blob = bytearray(cipher.encrypt(COUPLE, CARD, "secret"))
    blob[index] ^= 0x01
    with pytest.raises(DecryptionError):
        cipher.decrypt(COUPLE, CARD, bytes(blob))


@pytest.mark.req("REQ-N-SEC-05")
def test_truncated_value_fails() -> None:
    with pytest.raises(DecryptionError):
        _setup()[0].decrypt(COUPLE, CARD, b"\x01\x00")


@pytest.mark.req("REQ-N-SEC-05")
def test_kek_rewrap_keeps_values_readable() -> None:
    cipher, store, old_kek, clock = _setup()
    blob = cipher.encrypt(COUPLE, CARD, "before rotation")
    new_kek = Kek(os.urandom(32))
    store.save(COUPLE, rewrap(COUPLE, store.current(COUPLE), old_kek, new_kek))
    assert store.get(COUPLE, 99) is None
    rotated = AesGcmCipher(store, new_kek, clock)
    assert rotated.decrypt(COUPLE, CARD, blob) == "before rotation"
    with pytest.raises(DecryptionError):
        AesGcmCipher(store, old_kek, clock).decrypt(COUPLE, CARD, blob)


@pytest.mark.req("REQ-N-SEC-05")
def test_wrapped_dek_cannot_move_to_another_couple() -> None:
    kek = Kek(os.urandom(32))
    wrapped = kek.wrap(COUPLE, 1, new_dek())
    with pytest.raises(DecryptionError):
        kek.unwrap(OTHER_COUPLE, wrapped)


@pytest.mark.req("REQ-N-SEC-05")
def test_new_key_id_writes_new_values_and_old_ones_stay_readable() -> None:
    cipher, store, kek, _ = _setup()
    old_blob = cipher.encrypt(COUPLE, CARD, "old")
    store.save(COUPLE, kek.wrap(COUPLE, 2, new_dek()))
    new_blob = cipher.encrypt(COUPLE, CARD, "new")
    assert int.from_bytes(new_blob[1:5], "big") == 2
    assert cipher.decrypt(COUPLE, CARD, old_blob) == "old"
    assert cipher.decrypt(COUPLE, CARD, new_blob) == "new"


@pytest.mark.req("REQ-N-SEC-05")
def test_unwrapped_deks_are_cached_for_five_minutes_then_refetched() -> None:
    cipher, store, _, clock = _setup()
    blob = cipher.encrypt(COUPLE, CARD, "x")
    reads_after_first = store.reads
    cipher.decrypt(COUPLE, CARD, blob)
    clock.advance(timedelta(minutes=4))
    cipher.decrypt(COUPLE, CARD, blob)
    assert store.reads == reads_after_first + 2, "the store is read, but the KEK unwrap is cached"
    cipher.forget(COUPLE)
    clock.advance(timedelta(minutes=6))
    assert cipher.decrypt(COUPLE, CARD, blob) == "x"


@pytest.mark.req("REQ-N-SEC-05")
def test_kek_must_be_256_bits() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        Kek(os.urandom(16))
    assert isinstance(Kek.from_base64(base64.b64encode(os.urandom(32)).decode()), Kek)


@pytest.mark.req("REQ-N-SEC-05")
@pytest.mark.parametrize("value", ["", "not base64!", base64.b64encode(os.urandom(16)).decode()])
def test_startup_check_rejects_a_malformed_kek(value: str) -> None:
    with override_settings(KEK=value):
        assert [message.id for message in kek_is_256_bits()] == ["cherrylove.E003"]


@pytest.mark.req("REQ-N-SEC-05")
def test_startup_check_accepts_the_configured_kek() -> None:
    assert kek_is_256_bits() == []

"""Couple data key store on PostgreSQL (IMPL-API-001 F2.4; ADR-009 §1, REQ-N-SEC-05)."""

from __future__ import annotations

import os
import uuid

import pytest
from django.db import connections

from cherrylove.identity.infrastructure.orm import Couple
from cherrylove.shared.application.cipher import DekStore, FieldLocation, WrappedDek
from cherrylove.shared.domain.errors import NotFound
from cherrylove.shared.domain.ids import CoupleId
from cherrylove.shared.infrastructure.clock import SystemClock
from cherrylove.shared.infrastructure.crypto.aes_gcm import AesGcmCipher, Kek, new_dek
from cherrylove.shared.infrastructure.crypto.dek_store import DjangoDekStore, provision_couple_key

pytestmark = pytest.mark.integration


def _couple() -> CoupleId:
    return CoupleId(Couple.objects.create().id)


@pytest.mark.req("REQ-N-SEC-05")
@pytest.mark.django_db
def test_the_database_holds_only_the_wrapped_key() -> None:
    store: DekStore = DjangoDekStore()
    kek, couple, dek = Kek(os.urandom(32)), _couple(), new_dek()
    store.save(couple, kek.wrap(couple, 1, dek))
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT wrapped_dek FROM shared_couple_data_key WHERE couple_id = %s", [couple.value])
        row = cursor.fetchone()
    assert row is not None
    raw = bytes(row[0])
    assert dek not in raw
    assert kek.unwrap(couple, WrappedDek(1, raw)) == dek


@pytest.mark.req("REQ-N-SEC-05")
@pytest.mark.django_db
def test_provisioned_key_encrypts_and_newest_key_id_is_current() -> None:
    store, kek, couple = DjangoDekStore(), Kek(os.urandom(32)), _couple()
    provision_couple_key(store, kek, couple)
    cipher = AesGcmCipher(store, kek, SystemClock())
    where = FieldLocation("card", uuid.uuid7(), "body")
    blob = cipher.encrypt(couple, where, "secret")
    assert cipher.decrypt(couple, where, blob) == "secret"
    store.save(couple, kek.wrap(couple, 2, new_dek()))
    assert store.current(couple).key_id == 2
    assert store.get(couple, 1) is not None
    assert store.get(couple, 9) is None


@pytest.mark.req("REQ-N-SEC-05")
@pytest.mark.django_db
def test_a_couple_without_a_key_is_not_found() -> None:
    with pytest.raises(NotFound):
        DjangoDekStore().current(_couple())

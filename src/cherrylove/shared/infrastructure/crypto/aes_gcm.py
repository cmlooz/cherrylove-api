"""AES-256-GCM envelope encryption (ADR-009 §1-3, §6; REQ-N-SEC-05).

Stored value: `version (1 byte) | key_id (4 bytes, big-endian) | nonce (12 bytes) | ciphertext + tag (16)`.
AAD of a value: `couple_id | entity_type | entity_id | field`. DEKs are wrapped by the KEK with AAD
`couple_id | key_id`, so a wrapped key cannot be moved to another couple either. Unwrapped DEKs live in an
in-process LRU for 5 minutes, never in Redis.
"""

from __future__ import annotations

import base64
import os
import struct
from collections import OrderedDict
from datetime import datetime, timedelta

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from cherrylove.shared.application.cipher import DecryptionError, DekStore, FieldLocation, WrappedDek
from cherrylove.shared.domain.clock import Clock
from cherrylove.shared.domain.ids import CoupleId

VERSION = 1
KEY_BYTES = 32
NONCE_BYTES = 12
HEADER = struct.Struct(">BI")  # version, key_id
DEK_CACHE_TTL = timedelta(minutes=5)
DEK_CACHE_SIZE = 1024


class Kek:
    """The key-encryption key: 256 bits from the environment, never stored in the database."""

    def __init__(self, key: bytes) -> None:
        if len(key) != KEY_BYTES:
            raise ValueError("the KEK must be 32 bytes (256 bits)")
        self._aead = AESGCM(key)

    @classmethod
    def from_base64(cls, value: str) -> Kek:
        return cls(base64.b64decode(value, validate=True))

    def wrap(self, couple_id: CoupleId, key_id: int, dek: bytes) -> WrappedDek:
        nonce = os.urandom(NONCE_BYTES)
        return WrappedDek(key_id, nonce + self._aead.encrypt(nonce, dek, _dek_aad(couple_id, key_id)))

    def unwrap(self, couple_id: CoupleId, dek: WrappedDek) -> bytes:
        nonce, sealed = dek.wrapped[:NONCE_BYTES], dek.wrapped[NONCE_BYTES:]
        try:
            return self._aead.decrypt(nonce, sealed, _dek_aad(couple_id, dek.key_id))
        except InvalidTag:
            raise DecryptionError("cannot unwrap data key") from None


def new_dek() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def rewrap(couple_id: CoupleId, dek: WrappedDek, old: Kek, new: Kek) -> WrappedDek:
    """KEK rotation (ADR-009 §6): the DEK itself, and every value it encrypted, stays the same."""
    return new.wrap(couple_id, dek.key_id, old.unwrap(couple_id, dek))


def _dek_aad(couple_id: CoupleId, key_id: int) -> bytes:
    return f"{couple_id}|{key_id}".encode()


def _value_aad(couple_id: CoupleId, where: FieldLocation) -> bytes:
    return f"{couple_id}|{where.entity_type}|{where.entity_id}|{where.field}".encode()


class AesGcmCipher:
    def __init__(self, store: DekStore, kek: Kek, clock: Clock) -> None:
        self._store = store
        self._kek = kek
        self._clock = clock
        self._cache: OrderedDict[tuple[CoupleId, int], tuple[datetime, AESGCM]] = OrderedDict()

    def encrypt(self, couple_id: CoupleId, where: FieldLocation, plaintext: str) -> bytes:
        dek = self._store.current(couple_id)
        nonce = os.urandom(NONCE_BYTES)
        sealed = self._aead(couple_id, dek).encrypt(nonce, plaintext.encode(), _value_aad(couple_id, where))
        return HEADER.pack(VERSION, dek.key_id) + nonce + sealed

    def decrypt(self, couple_id: CoupleId, where: FieldLocation, blob: bytes) -> str:
        if len(blob) < HEADER.size + NONCE_BYTES + 16:
            raise DecryptionError("value too short")
        version, key_id = HEADER.unpack_from(blob)
        if version != VERSION:
            raise DecryptionError("unknown format version")
        nonce = blob[HEADER.size : HEADER.size + NONCE_BYTES]
        sealed = blob[HEADER.size + NONCE_BYTES :]
        dek = self._store.get(couple_id, key_id)
        if dek is None:
            raise DecryptionError("cannot decrypt value")
        aead = self._aead(couple_id, dek)
        try:
            return aead.decrypt(nonce, sealed, _value_aad(couple_id, where)).decode()
        except InvalidTag:
            raise DecryptionError("cannot decrypt value") from None

    def _aead(self, couple_id: CoupleId, dek: WrappedDek) -> AESGCM:
        cache_key = (couple_id, dek.key_id)
        now = self._clock.now()
        cached = self._cache.get(cache_key)
        if cached is not None and now - cached[0] < DEK_CACHE_TTL:
            self._cache.move_to_end(cache_key)
            return cached[1]
        aead = AESGCM(self._kek.unwrap(couple_id, dek))
        self._cache[cache_key] = (now, aead)
        self._cache.move_to_end(cache_key)
        while len(self._cache) > DEK_CACHE_SIZE:
            self._cache.popitem(last=False)
        return aead

    def forget(self, couple_id: CoupleId) -> None:
        """Drop cached keys of a couple (purge, ADR-009 §5)."""
        for cache_key in [key for key in self._cache if key[0] == couple_id]:
            del self._cache[cache_key]

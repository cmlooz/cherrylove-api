"""Reversible fake Cipher that still binds a value to its place (ADR-009 §2), for DB-free use-case tests."""

from __future__ import annotations

from cherrylove.shared.application.cipher import DecryptionError, FieldLocation
from cherrylove.shared.domain.ids import CoupleId


class FakeCipher:
    def encrypt(self, couple_id: CoupleId, where: FieldLocation, plaintext: str) -> bytes:
        return f"{self._aad(couple_id, where)}::{plaintext}".encode()

    def decrypt(self, couple_id: CoupleId, where: FieldLocation, blob: bytes) -> str:
        prefix, separator, plaintext = blob.decode().partition("::")
        if not separator or prefix != self._aad(couple_id, where):
            raise DecryptionError("cannot decrypt value")
        return plaintext

    @staticmethod
    def _aad(couple_id: CoupleId, where: FieldLocation) -> str:
        return f"{couple_id}|{where.entity_type}|{where.entity_id}|{where.field}"

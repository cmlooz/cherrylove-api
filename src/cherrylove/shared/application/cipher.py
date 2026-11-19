"""Cipher and data-key store ports (ADR-009 §1-3, REQ-N-SEC-05).

Encryption happens only in repository mappers and query services (infrastructure); domain entities hold
plain strings. Each value is bound to where it lives through its associated data, so a ciphertext copied to
another row, field or couple does not decrypt.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from cherrylove.shared.domain.ids import CoupleId


class DecryptionError(ValueError):
    """Wrong key, wrong place (AAD) or tampered bytes. Never says which."""


@dataclass(frozen=True, slots=True)
class FieldLocation:
    """Where an encrypted value lives; it becomes the AEAD associated data."""

    entity_type: str
    entity_id: uuid.UUID
    field: str


@dataclass(frozen=True, slots=True)
class WrappedDek:
    key_id: int
    wrapped: bytes


class DekStore(Protocol):
    """One data key per couple, stored wrapped by the KEK (table `shared_couple_data_key`, F2.4)."""

    def current(self, couple_id: CoupleId) -> WrappedDek: ...

    def get(self, couple_id: CoupleId, key_id: int) -> WrappedDek | None:
        """None for an unknown key_id: the cipher reports it like any other bad value."""
        ...

    def save(self, couple_id: CoupleId, dek: WrappedDek) -> None: ...


class Cipher(Protocol):
    def encrypt(self, couple_id: CoupleId, where: FieldLocation, plaintext: str) -> bytes: ...

    def decrypt(self, couple_id: CoupleId, where: FieldLocation, blob: bytes) -> str: ...

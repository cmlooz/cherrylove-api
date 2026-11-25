"""Identity ports (ADR-002 §1): repositories and gateways the use cases depend on."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol

from cherrylove.identity.domain.invite import InviteSnapshot, Slot
from cherrylove.shared.domain.ids import CoupleId, UserId


class MembershipQuery(Protocol):
    def emails_in_a_couple(self, emails: Iterable[str]) -> set[str]:
        """The subset of `emails` (lower-case) whose user already belongs to a couple."""
        ...


class CoupleRepository(Protocol):
    def add(self, couple_id: CoupleId) -> None: ...


class InviteRepository(Protocol):
    def add_pending(
        self, invite_id: uuid.UUID, couple_id: CoupleId, slot: Slot, email: str, expires_at: datetime
    ) -> None:
        """A pending invite without a token yet: the send-email job issues it (ADR-004 §4)."""
        ...

    def get(self, invite_id: uuid.UUID) -> InviteSnapshot | None: ...

    def pending_for_seat(self, couple_id: CoupleId, slot: Slot) -> InviteSnapshot | None: ...

    def revoke(self, invite_id: uuid.UUID) -> None: ...

    def set_token(self, invite_id: uuid.UUID, token_hash: bytes, sent_at: datetime) -> None:
        """Only the SHA-256 of the token is stored (ADR-004 §4)."""
        ...


class TokenGenerator(Protocol):
    def new(self) -> str:
        """A URL-safe token from 32 random bytes."""
        ...


class CoupleProvisioner(Protocol):
    """Everything another module must create together with a couple (sync_state, data key)."""

    def provision(self, couple_id: CoupleId) -> None: ...


class InviteMailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


@dataclass(frozen=True, slots=True)
class InviteContext:
    """An invite found by its token hash, with what accepting it depends on."""

    invite: InviteSnapshot
    couple_archived: bool
    seat_taken: bool
    relationship_start: date | None


class InviteLookup(Protocol):
    def by_token_hash(self, token_hash: bytes) -> InviteContext | None: ...


@dataclass(frozen=True, slots=True)
class NewPartner:
    email: str
    name: str
    birth_date: date
    password: str
    language: str


class PartnerRepository(Protocol):
    def add(self, user_id: UserId, partner: NewPartner, couple_id: CoupleId, slot: Slot) -> None:
        """User (password hashed by the adapter) and membership, in the current transaction."""
        ...

    def accept_invite(self, invite_id: uuid.UUID, accepted_at: datetime) -> None: ...

    def set_relationship_start(self, couple_id: CoupleId, relationship_start: date) -> None:
        """Only when the couple has none yet: the first partner decides it (REQ-F-AUTH-04)."""
        ...


@dataclass(frozen=True, slots=True)
class Session:
    access: str
    access_expires_at: datetime
    refresh: str
    refresh_expires_at: datetime


class TokenIssuer(Protocol):
    def issue(self, user_id: UserId) -> Session: ...


@dataclass(frozen=True, slots=True)
class Account:
    """What login needs to know about a verified account; nothing about its content."""

    user_id: UserId
    couple_id: CoupleId
    couple_archived: bool


class CredentialCheck(Protocol):
    def verify(self, email: str, password: str) -> Account | None:
        """The partner account behind valid credentials, or None (unknown email, wrong password, inactive
        user, staff or no couple). The password check runs even for unknown emails (no timing oracle)."""
        ...


@dataclass(frozen=True, slots=True)
class RefreshCheck:
    """`reused`: a well-signed refresh that was already rotated or revoked, i.e. a stolen copy (ADR-004 §3)."""

    kind: Literal["valid", "reused", "invalid"]
    user_id: UserId | None = None


class SessionStore(Protocol):
    def check(self, refresh: str) -> RefreshCheck: ...

    def revoke_all(self, user_id: UserId) -> int:
        """Blacklist every outstanding refresh of the user; how many were still live."""
        ...

    def rotate(self, refresh: str) -> tuple[UserId, Session]:
        """Blacklist `refresh` and return a new pair; raises NotAuthenticated when it is not usable."""
        ...

    def revoke(self, refresh: str) -> UserId | None:
        """Blacklist `refresh`; the owner, or None when it was already unusable."""
        ...

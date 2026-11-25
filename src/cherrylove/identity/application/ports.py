"""Identity ports (ADR-002 §1): repositories and gateways the use cases depend on."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from cherrylove.identity.domain.invite import Slot
from cherrylove.shared.domain.ids import CoupleId


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


class CoupleProvisioner(Protocol):
    """Everything another module must create together with a couple (sync_state, data key)."""

    def provision(self, couple_id: CoupleId) -> None: ...

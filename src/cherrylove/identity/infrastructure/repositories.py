"""Django adapters of the identity ports (ADR-002 §1)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime

from cherrylove.identity.domain.invite import Slot
from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, Invite
from cherrylove.shared.domain.ids import CoupleId


class DjangoMembershipQuery:
    def emails_in_a_couple(self, emails: Iterable[str]) -> set[str]:
        found = CoupleMembership.objects.filter(user__email__in=list(emails)).values_list("user__email", flat=True)
        return set(found)


class DjangoCoupleRepository:
    def add(self, couple_id: CoupleId) -> None:
        Couple(id=couple_id.value).save(force_insert=True)


class DjangoInviteRepository:
    def add_pending(
        self, invite_id: uuid.UUID, couple_id: CoupleId, slot: Slot, email: str, expires_at: datetime
    ) -> None:
        invite = Invite(id=invite_id, couple_id=couple_id.value, slot=slot, email=email, expires_at=expires_at)
        invite.save(force_insert=True)

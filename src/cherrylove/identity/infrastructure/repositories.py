"""Django adapters of the identity ports (ADR-002 §1)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime

from cherrylove.identity.domain.invite import InviteSnapshot, Slot
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

    def get(self, invite_id: uuid.UUID) -> InviteSnapshot | None:
        row = Invite.objects.filter(id=invite_id).first()
        return _snapshot(row) if row else None

    def pending_for_seat(self, couple_id: CoupleId, slot: Slot) -> InviteSnapshot | None:
        row = Invite.objects.filter(couple_id=couple_id.value, slot=slot, status=Invite.Status.PENDING).first()
        return _snapshot(row) if row else None

    def revoke(self, invite_id: uuid.UUID) -> None:
        Invite.objects.filter(id=invite_id, status=Invite.Status.PENDING).update(status=Invite.Status.REVOKED)

    def set_token(self, invite_id: uuid.UUID, token_hash: bytes, sent_at: datetime) -> None:
        Invite.objects.filter(id=invite_id).update(token_hash=token_hash, sent_at=sent_at)


def _snapshot(row: Invite) -> InviteSnapshot:
    slot: Slot = 1 if row.slot == 1 else 2
    return InviteSnapshot(row.id, CoupleId(row.couple_id), slot, row.email, row.status, row.expires_at)  # type: ignore[arg-type]

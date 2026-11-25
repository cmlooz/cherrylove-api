"""Django adapters of the identity ports (ADR-002 §1)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date, datetime

from cherrylove.identity.application.ports import Account, InviteContext, NewPartner
from cherrylove.identity.domain.invite import InviteSnapshot, Slot
from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, Invite, User
from cherrylove.shared.domain.ids import CoupleId, UserId


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


class DjangoInviteLookup:
    def by_token_hash(self, token_hash: bytes) -> InviteContext | None:
        row = Invite.objects.select_related("couple").filter(token_hash=token_hash).first()
        if row is None:
            return None
        seat_taken = CoupleMembership.objects.filter(couple_id=row.couple_id, slot=row.slot).exists()
        return InviteContext(
            invite=_snapshot(row),
            couple_archived=row.couple.status == Couple.Status.ARCHIVED,
            seat_taken=seat_taken,
            relationship_start=row.couple.relationship_start,
        )


class DjangoPartnerRepository:
    def add(self, user_id: UserId, partner: NewPartner, couple_id: CoupleId, slot: Slot) -> None:
        user = User(id=user_id.value, email=partner.email, name=partner.name, birth_date=partner.birth_date)
        user.language = partner.language
        user.set_password(partner.password)  # Argon2 (ADR-004 §4)
        user.save(force_insert=True)
        CoupleMembership.objects.create(couple_id=couple_id.value, user_id=user_id.value, slot=slot)

    def accept_invite(self, invite_id: uuid.UUID, accepted_at: datetime) -> None:
        Invite.objects.filter(id=invite_id, status=Invite.Status.PENDING).update(
            status=Invite.Status.ACCEPTED, accepted_at=accepted_at
        )

    def set_relationship_start(self, couple_id: CoupleId, relationship_start: date) -> None:
        Couple.objects.filter(id=couple_id.value, relationship_start__isnull=True).update(
            relationship_start=relationship_start
        )


class DjangoCredentialCheck:
    def verify(self, email: str, password: str) -> Account | None:
        user = User.objects.filter(email=email).select_related("membership__couple").first()
        if user is None:
            User().set_password(password)  # same Argon2 cost as a real check (Django ModelBackend does this)
            return None
        if not user.check_password(password) or not user.is_active or user.is_staff or user.is_superuser:
            return None
        membership = CoupleMembership.objects.select_related("couple").filter(user_id=user.id).first()
        if membership is None:
            return None
        return Account(
            UserId(user.id), CoupleId(membership.couple_id), membership.couple.status == Couple.Status.ARCHIVED
        )


class DjangoAccountStatus:
    def deactivate(self, user_id: UserId) -> bool | None:
        user = User.objects.select_for_update().filter(id=user_id.value).only("is_active").first()
        if user is None:
            return None
        was_active = user.is_active
        User.objects.filter(id=user_id.value).update(is_active=False)
        return was_active

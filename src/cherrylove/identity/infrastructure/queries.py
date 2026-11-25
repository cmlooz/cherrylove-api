"""Read-side adapters (CQRS-lite): every query is scoped by the Actor's couple (ADR-005)."""

from __future__ import annotations

from cherrylove.identity.application.queries.profile import CoupleRow, MeView, PersonSummary
from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, User
from cherrylove.shared.domain.errors import NotFound
from cherrylove.shared.domain.ids import CoupleId, UserId


def _members(couple_id: CoupleId) -> list[User]:
    """The couple's users in slot order (one query)."""
    memberships = (
        CoupleMembership.objects.filter(couple_id=couple_id.value)
        .order_by("slot")
        .select_related("user")
        .only(
            "slot",
            "user__id",
            "user__email",
            "user__name",
            "user__birth_date",
            "user__language",
            "user__avatar_media_id",
        )
    )
    return [membership.user for membership in memberships]


def _summary(user: User) -> PersonSummary:
    return PersonSummary(user.id, user.name, user.avatar_media_id)


class DjangoProfileQuery:
    def me(self, couple_id: CoupleId, user_id: UserId) -> MeView:
        members = _members(couple_id)
        me = next((user for user in members if user.id == user_id.value), None)
        if me is None:
            raise NotFound("no such member")
        partner = next((_summary(user) for user in members if user.id != user_id.value), None)
        return MeView(me.id, me.email, me.name, me.birth_date, me.language, me.avatar_media_id, partner)

    def couple(self, couple_id: CoupleId) -> CoupleRow:
        couple = Couple.objects.filter(id=couple_id.value).only("relationship_start", "timezone", "version").first()
        if couple is None:
            raise NotFound("no such couple")
        partners = tuple(_summary(user) for user in _members(couple_id))
        return CoupleRow(couple.id, partners, couple.relationship_start, couple.timezone, couple.version)

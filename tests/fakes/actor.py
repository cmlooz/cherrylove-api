"""In-memory ActorResolver (ADR-005 §1, ADR-014 §1)."""

from __future__ import annotations

from cherrylove.shared.domain.actor import ActorResolver, Membership
from cherrylove.shared.domain.errors import NotFound
from cherrylove.shared.domain.ids import UserId


class InMemoryActorResolver(ActorResolver):
    def __init__(self, *memberships: Membership) -> None:
        self.memberships = {m.user_id: m for m in memberships}

    def _membership_for(self, user_id: UserId) -> Membership:
        membership = self.memberships.get(user_id)
        if membership is None:
            raise NotFound("no membership")
        return membership

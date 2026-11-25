"""The identity implementation of `ActorResolver` (ADR-005 §1, ADR-011 §1, REQ-N-SEC-01).

A partner is an active, non-staff user with a membership in an active couple. The membership is cached as
`actor:{user_id}` for 10 minutes (the access-token lifetime), so a request with a valid access token costs no
query; anything that ends a partner's rights deletes the key (F2.15, F9.4). Only positive answers are cached:
a refused user is looked up again on every request. The cache fails open (ADR-011 §2), so an outage only
costs the query.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from cherrylove.identity.infrastructure.orm import Couple, User
from cherrylove.shared.application.cache import Cache
from cherrylove.shared.domain.actor import ActorResolver, Locale, Membership
from cherrylove.shared.domain.errors import NotAuthenticated
from cherrylove.shared.domain.ids import CoupleId, UserId

ACTOR_TTL = timedelta(minutes=10)


def actor_key(user_id: UserId) -> str:
    return f"actor:{user_id.value}"


def _load(user_id: UserId) -> dict[str, str]:
    row = (
        User.objects.filter(
            id=user_id.value,
            is_active=True,
            is_staff=False,
            membership__couple__status=Couple.Status.ACTIVE,
        )
        .values_list("membership__couple_id", "language")
        .first()
    )
    if row is None:
        raise NotAuthenticated("not an active partner of an active couple")
    return {"couple_id": str(row[0]), "locale": row[1]}


def _locale(value: str) -> Locale:
    return "en" if value == "en" else "es"


class CachedActorResolver(ActorResolver):
    def __init__(self, cache: Cache) -> None:
        self._cache = cache

    def _membership_for(self, user_id: UserId) -> Membership:
        cached = self._cache.get_or_compute(actor_key(user_id), lambda: _load(user_id), ACTOR_TTL)
        return Membership(user_id, CoupleId(uuid.UUID(cached["couple_id"])), _locale(cached["locale"]))

    def forget(self, user_id: UserId) -> None:
        self._cache.delete(actor_key(user_id))

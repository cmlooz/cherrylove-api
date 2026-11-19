"""Who is acting (ADR-005 §1, REQ-N-SEC-01).

An `Actor` is built once per request from the authenticated user's membership, **never** from a URL, body or
header. The constructor demands a capability that only `ActorResolver.resolve` holds, so code cannot fabricate
an Actor from request data; resolver adapters (F2.14) only say how to load a membership.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Final, Literal, final

from cherrylove.shared.domain.ids import CoupleId, UserId

type Locale = Literal["es", "en"]


class _Capability:
    __slots__ = ()


_ISSUE: Final = _Capability()


@dataclass(frozen=True, slots=True)
class Membership:
    """What the server knows about the user: loaded from the database (or its cache), not from the request."""

    user_id: UserId
    couple_id: CoupleId
    locale: Locale


@final
@dataclass(frozen=True, slots=True, init=False)
class Actor:
    user_id: UserId
    couple_id: CoupleId
    locale: Locale

    def __init__(self, membership: Membership, *, capability: _Capability) -> None:
        if capability is not _ISSUE:
            raise TypeError("an Actor is issued only by ActorResolver.resolve (ADR-005 §1)")
        object.__setattr__(self, "user_id", membership.user_id)
        object.__setattr__(self, "couple_id", membership.couple_id)
        object.__setattr__(self, "locale", membership.locale)

    def __replace__(self, **changes: object) -> Actor:
        raise TypeError("an Actor cannot be copied with changes")


class ActorResolver(ABC):
    """Port: the server-side source of the Actor (identity implements it in F2.14)."""

    @final
    def resolve(self, user_id: UserId) -> Actor:
        return Actor(self._membership_for(user_id), capability=_ISSUE)

    @abstractmethod
    def _membership_for(self, user_id: UserId) -> Membership:
        """Load the membership or raise a domain error (inactive user, no couple, archived couple)."""

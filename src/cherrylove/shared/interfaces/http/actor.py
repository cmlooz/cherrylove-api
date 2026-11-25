"""The request's Actor at the HTTP edge (ADR-005 §1, REQ-N-SEC-01).

Authentication puts a `Partner` in `request.user`: it holds only the Actor the server resolved from the
token's subject, never anything read from the URL, body or headers. Views of partner routes declare
`IsCouplePartner` and read the Actor with `actor_of(request)`.
"""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from cherrylove.shared.domain.actor import Actor


class Partner:
    """`request.user` on partner routes: an authenticated principal with no ORM row behind it."""

    is_authenticated = True
    is_anonymous = False
    is_active = True

    def __init__(self, actor: Actor) -> None:
        self.actor = actor

    @property
    def pk(self) -> uuid.UUID:
        return self.actor.user_id.value

    @property
    def id(self) -> uuid.UUID:
        return self.actor.user_id.value


class IsCouplePartner(BasePermission):
    """Active user, in a couple, couple active: checked when the Actor was resolved."""

    def has_permission(self, request: Request, view: Any) -> bool:
        return isinstance(request.user, Partner)


def actor_of(request: Request) -> Actor:
    user = request.user
    if not isinstance(user, Partner):
        raise TypeError("actor_of needs a view protected by IsCouplePartner")
    return user.actor

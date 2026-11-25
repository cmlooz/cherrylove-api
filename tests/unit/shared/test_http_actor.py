"""The HTTP edge of the Actor (IMPL-API-001 F2.14; ADR-005 §1, REQ-N-SEC-01)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.auth.models import AnonymousUser

from cherrylove.shared.domain.actor import Actor, ActorResolver, Membership
from cherrylove.shared.domain.ids import CoupleId, UserId
from cherrylove.shared.interfaces.http.actor import IsCouplePartner, Partner, actor_of


class _Resolver(ActorResolver):
    def _membership_for(self, user_id: UserId) -> Membership:
        return Membership(user_id, CoupleId(uuid.uuid4()), "en")


def _request(user: object) -> Any:
    return SimpleNamespace(user=user)


def _actor() -> Actor:
    return _Resolver().resolve(UserId(uuid.uuid4()))


@pytest.mark.req("REQ-N-SEC-01")
def test_only_a_resolved_partner_passes_is_couple_partner() -> None:
    permission = IsCouplePartner()
    assert permission.has_permission(_request(Partner(_actor())), None)
    assert not permission.has_permission(_request(AnonymousUser()), None)


@pytest.mark.req("REQ-N-SEC-01")
def test_actor_of_returns_the_resolved_actor_and_refuses_anything_else() -> None:
    actor = _actor()
    partner = Partner(actor)
    assert actor_of(_request(partner)) is actor
    assert (partner.pk, partner.is_authenticated) == (actor.user_id.value, True)
    with pytest.raises(TypeError):
        actor_of(_request(AnonymousUser()))

"""Actor resolution with the cached membership (IMPL-API-001 F2.14; ADR-005 §1, ADR-011 §1, REQ-N-SEC-01)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone
from pytest_django import DjangoAssertNumQueries

from cherrylove.identity import wiring
from cherrylove.identity.infrastructure.adapters.actor_resolver import actor_key
from cherrylove.identity.infrastructure.adapters.jwt_tokens import JwtTokenIssuer
from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, User
from cherrylove.shared.domain.errors import NotAuthenticated
from cherrylove.shared.domain.ids import UserId
from cherrylove.shared.infrastructure.redis_cache import redis_client

pytestmark = pytest.mark.integration
PASSWORD = "correct horse battery"
REDIS = redis_client(settings.REDIS_URL)


def _partner(*, couple: Couple | None = None, language: str = "en", **fields: Any) -> User:
    user = User.objects.create_user(
        f"a.{uuid.uuid4().hex[:8]}@example.com", PASSWORD, name="A", language=language, **fields
    )
    CoupleMembership.objects.create(couple=couple or Couple.objects.create(), user=user, slot=1)
    return user


def _archived() -> Couple:
    return Couple.objects.create(status=Couple.Status.ARCHIVED, archived_at=timezone.now())


def _cached(user: User) -> str:
    return "cl:" + actor_key(UserId(user.id))


@pytest.mark.req("REQ-N-SEC-01")
@pytest.mark.django_db(transaction=True)
def test_a_partner_resolves_to_their_couple_and_the_second_time_costs_no_query(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    user = _partner()
    resolver = wiring.actor_resolver()
    actor = resolver.resolve(UserId(user.id))
    assert (actor.user_id.value, actor.couple_id.value, actor.locale) == (user.id, user.membership.couple_id, "en")
    with django_assert_num_queries(0):
        assert resolver.resolve(UserId(user.id)) == actor
    assert REDIS.ttl(_cached(user)) in range(1, 601)


@pytest.mark.req("REQ-N-SEC-01")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("case", ["inactive", "archived", "no_couple"])
def test_anyone_but_an_active_partner_is_refused_and_not_cached(case: str) -> None:
    # Staff are never partners: a database trigger refuses the membership (F2.2).
    if case == "no_couple":
        user = User.objects.create_user(f"n.{uuid.uuid4().hex[:8]}@example.com", PASSWORD, name="N")
    elif case == "archived":
        user = _partner(couple=_archived())
    else:
        user = _partner(is_active=False)
    with pytest.raises(NotAuthenticated):
        wiring.actor_resolver().resolve(UserId(user.id))
    assert REDIS.exists(_cached(user)) == 0


@pytest.mark.req("REQ-N-SEC-01")
@pytest.mark.django_db(transaction=True)
def test_a_valid_access_token_of_a_user_of_an_archived_couple_is_refused(client: Client) -> None:
    user = _partner(couple=_archived())
    access = JwtTokenIssuer().issue(UserId(user.id)).access
    logout = client.post(
        "/api/v1/auth/logout", content_type="application/json", headers={"Authorization": f"Bearer {access}"}
    )
    assert (logout.status_code, logout.json()["code"]) == (401, "not_authenticated")

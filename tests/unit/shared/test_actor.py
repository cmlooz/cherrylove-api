"""The Actor is immutable and only a resolver can issue it (IMPL-API-001 F1.2, ADR-005 §1)."""

from __future__ import annotations

import copy
import dataclasses

import pytest

from cherrylove.shared.domain.actor import Actor, Membership
from cherrylove.shared.domain.errors import NotFound
from cherrylove.shared.domain.ids import CoupleId, UserId
from tests.fakes.actor import InMemoryActorResolver
from tests.fakes.clock import FixedClock, SequentialIdGenerator

IDS = SequentialIdGenerator(FixedClock())
USER = UserId(IDS.new())
COUPLE = CoupleId(IDS.new())
MEMBERSHIP = Membership(USER, COUPLE, "es")


@pytest.mark.req("REQ-N-SEC-01")
def test_resolver_issues_the_actor_from_the_membership() -> None:
    actor = InMemoryActorResolver(MEMBERSHIP).resolve(USER)
    assert (actor.user_id, actor.couple_id, actor.locale) == (USER, COUPLE, "es")


@pytest.mark.req("REQ-N-SEC-01")
def test_unknown_user_gets_no_actor() -> None:
    with pytest.raises(NotFound):
        InMemoryActorResolver().resolve(USER)


@pytest.mark.req("REQ-N-SEC-01")
@pytest.mark.parametrize(
    "build",
    [
        lambda: Actor(MEMBERSHIP),  # type: ignore[call-arg]
        lambda: Actor(MEMBERSHIP, capability=object()),  # type: ignore[arg-type]
        lambda: Actor(user_id=USER, couple_id=COUPLE, locale="es"),  # type: ignore[call-arg]
    ],
    ids=["no-capability", "forged-capability", "fields-from-request"],
)
def test_actor_cannot_be_built_outside_a_resolver(build: object) -> None:
    with pytest.raises(TypeError):
        build()  # type: ignore[operator]


@pytest.mark.req("REQ-N-SEC-01")
def test_actor_is_immutable_and_cannot_be_copied_with_changes() -> None:
    actor = InMemoryActorResolver(MEMBERSHIP).resolve(USER)
    with pytest.raises(dataclasses.FrozenInstanceError):
        actor.couple_id = CoupleId(IDS.new())  # type: ignore[misc]
    with pytest.raises(TypeError):
        copy.replace(actor, couple_id=CoupleId(IDS.new()))
    with pytest.raises(TypeError):
        dataclasses.replace(actor, couple_id=CoupleId(IDS.new()))


@pytest.mark.req("REQ-N-SEC-01")
def test_same_membership_gives_equal_actors() -> None:
    resolver = InMemoryActorResolver(MEMBERSHIP)
    assert resolver.resolve(USER) == resolver.resolve(USER)

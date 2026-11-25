"""Couple B's token on couple A's resources → 404, for every registered route (IMPL-API-001 F2.17; ADR-005 §7).

The parameter list comes from `tests/cross_couple.py`; the architecture test makes sure every route with a
path parameter is there. Identity has no couple-owned ID route yet, so the first factories arrive in F3.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import Client
from django.urls import reverse

from cherrylove.identity.infrastructure.adapters.jwt_tokens import JwtTokenIssuer
from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, User
from cherrylove.shared.domain.ids import UserId
from tests.cross_couple import FACTORIES, ResourceFactory

pytestmark = pytest.mark.integration


def _partner() -> tuple[Couple, User]:
    couple = Couple.objects.create()
    user = User.objects.create_user(f"x.{uuid.uuid4().hex[:8]}@example.com", "correct horse battery", name="X")
    CoupleMembership.objects.create(couple=couple, user=user, slot=1)
    return couple, user


@pytest.mark.req("REQ-N-SEC-02")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(("route", "factory"), sorted(FACTORIES.items()), ids=sorted(FACTORIES))
def test_another_couples_resource_does_not_exist_for_me(client: Client, route: str, factory: ResourceFactory) -> None:
    couple_a, author = _partner()
    url = reverse(route, kwargs=factory.create(couple_a, author))
    _, intruder = _partner()
    bearer = {"Authorization": f"Bearer {JwtTokenIssuer().issue(UserId(intruder.id)).access}"}
    for method in factory.methods:
        response = client.generic(method, url, "{}", content_type="application/json", headers=bearer)
        assert (response.status_code, response.json()["code"]) == (404, "not_found"), method

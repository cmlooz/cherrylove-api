"""No route escapes the cross-couple suite (IMPL-API-001 F2.17; ADR-005 §7, ADR-014 §5, REQ-N-SEC-02)."""

from __future__ import annotations

import pytest

from tests.cross_couple import FACTORIES, PUBLIC_ROUTES, api_routes


@pytest.mark.req("REQ-N-SEC-02")
def test_the_walker_sees_the_api_routes_and_their_parameters() -> None:
    routes = {route.name: route for route in api_routes()}
    assert routes["identity_get_invite"].parameters == ("token",)
    assert routes["home_get_couple"].parameters == ()


@pytest.mark.req("REQ-N-SEC-02")
def test_every_route_with_an_id_has_a_factory_or_a_public_reason() -> None:
    uncovered = [
        route.path
        for route in api_routes()
        if route.parameters and route.name not in FACTORIES and route.name not in PUBLIC_ROUTES
    ]
    assert uncovered == [], "add a ResourceFactory in tests/cross_couple.py (ADR-005 §7)"


@pytest.mark.req("REQ-N-SEC-02")
def test_public_routes_really_take_no_credentials_and_lists_have_no_stale_names() -> None:
    routes = {route.name: route for route in api_routes()}
    assert set(PUBLIC_ROUTES) | set(FACTORIES) <= set(routes)
    for name in PUBLIC_ROUTES:
        view = routes[name].callback.view_class
        assert view.authentication_classes == (), f"{name} authenticates, so it must have a factory"

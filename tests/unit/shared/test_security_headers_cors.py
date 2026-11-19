"""Security headers, CSP, no-store and single-origin CORS (IMPL-API-001 F1.9, REQ-N-SEC-07)."""

from __future__ import annotations

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory, override_settings

from cherrylove.shared.interfaces.http.middleware.security_headers import API_CSP, SecurityHeadersMiddleware

WEB = "http://localhost:5173"
EVIL = "https://evil.example"
PATH = "/no/such/path"  # any URL: the headers apply to every response, errors included


@pytest.mark.req("REQ-N-SEC-07")
def test_every_response_has_the_security_headers(client: Client) -> None:
    response = client.get(PATH)
    assert response["Content-Security-Policy"] == API_CSP
    assert "frame-ancestors 'none'" in response["Content-Security-Policy"]
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "no-referrer"
    assert response["X-Frame-Options"] == "DENY"
    assert response["Cache-Control"] == "no-store"


@pytest.mark.req("REQ-N-SEC-07")
def test_hsts_is_sent_over_https_with_production_values() -> None:
    with override_settings(SECURE_HSTS_SECONDS=31_536_000, SECURE_HSTS_INCLUDE_SUBDOMAINS=True):
        response = Client().get(PATH, secure=True)
    assert response["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


@pytest.mark.req("REQ-N-SEC-07")
def test_a_view_that_chooses_its_cache_policy_keeps_it() -> None:
    def view(request: HttpRequest) -> HttpResponse:
        response = HttpResponse()
        response["Cache-Control"] = "private, max-age=60"
        return response

    response = SecurityHeadersMiddleware(view)(RequestFactory().get("/"))
    assert response["Cache-Control"] == "private, max-age=60"
    assert response["Content-Security-Policy"] == API_CSP


@pytest.mark.req("REQ-N-SEC-07")
def test_preflight_from_the_web_origin_is_answered_with_credentials(client: Client) -> None:
    response = client.options(
        "/api/v1/cards/mine",
        headers={
            "Origin": WEB,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 204
    assert response["Access-Control-Allow-Origin"] == WEB
    assert response["Access-Control-Allow-Credentials"] == "true"
    assert "PUT" in response["Access-Control-Allow-Methods"]
    assert "X-CherryLove-Client" in response["Access-Control-Allow-Headers"]
    assert response["Access-Control-Max-Age"] == "600"
    assert "Origin" in response["Vary"]


@pytest.mark.req("REQ-N-SEC-07")
def test_simple_request_from_the_web_origin_exposes_request_id(client: Client) -> None:
    response = client.get(PATH, headers={"Origin": WEB})
    assert response["Access-Control-Allow-Origin"] == WEB
    assert response["Access-Control-Allow-Credentials"] == "true"
    assert "X-Request-ID" in response["Access-Control-Expose-Headers"]


@pytest.mark.req("REQ-N-SEC-07")
@pytest.mark.parametrize("origin", [EVIL, "http://localhost:5174", "null", WEB + "/"])
def test_other_origins_get_no_allow_headers(client: Client, origin: str) -> None:
    preflight = client.options(PATH, headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    simple = client.get(PATH, headers={"Origin": origin})
    for response in (preflight, simple):
        assert preflight.status_code != 204
        assert not [name for name in response.headers if name.lower().startswith("access-control-allow")]
        assert "Origin" in response["Vary"]

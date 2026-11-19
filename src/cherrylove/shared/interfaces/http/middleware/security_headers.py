"""Security headers for JSON responses (REQ-N-SEC-07, ADR-016 §1, ADR-011 §3).

Django's SecurityMiddleware already sends HSTS (production), `X-Content-Type-Options: nosniff` and the
referrer policy. This adds what Django 5.2 lacks: a CSP for an API that only serves JSON, and
`Cache-Control: no-store` on every response that did not choose its own policy (all API data is private).
The Django Admin gets its own CSP in F9.1.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class SecurityHeadersMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", API_CSP)
        response.headers.setdefault("Cache-Control", "no-store")
        return response

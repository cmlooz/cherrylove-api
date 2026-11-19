"""CORS for exactly one origin, the web app, with credentials (ADR-004 §2, REQ-N-SEC-07).

Own middleware instead of django-cors-headers (IMPL-API-001 F1 recommendation, REQ-N-ARC-06). Any other
origin gets no `Access-Control-Allow-*` header at all, so the browser blocks the call.
"""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.cache import patch_vary_headers

ALLOW_METHODS = "GET, POST, PUT, PATCH, DELETE"
ALLOW_HEADERS = "Authorization, Content-Type, X-Request-ID, X-CherryLove-Client"
EXPOSE_HEADERS = "X-Request-ID, Retry-After"
PREFLIGHT_MAX_AGE = "600"


class CorsMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.allowed_origin: str = settings.WEB_ORIGIN

    def __call__(self, request: HttpRequest) -> HttpResponse:
        origin = request.headers.get("Origin")
        allowed = origin == self.allowed_origin
        is_preflight = request.method == "OPTIONS" and "Access-Control-Request-Method" in request.headers
        if allowed and is_preflight:
            response = HttpResponse(status=204)
            response["Access-Control-Allow-Methods"] = ALLOW_METHODS
            response["Access-Control-Allow-Headers"] = ALLOW_HEADERS
            response["Access-Control-Max-Age"] = PREFLIGHT_MAX_AGE
        else:
            response = self.get_response(request)
        patch_vary_headers(response, ("Origin",))
        if allowed:
            response["Access-Control-Allow-Origin"] = self.allowed_origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Expose-Headers"] = EXPOSE_HEADERS
        return response

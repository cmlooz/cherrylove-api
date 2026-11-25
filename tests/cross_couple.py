"""Cross-couple harness, generated from the URL conf (ADR-005 §7, ADR-014 §5, REQ-N-SEC-02).

Every `/api/v1` route with a path parameter must be listed here: either with a `ResourceFactory` (the
integration suite then sends couple B's token to couple A's resource on every method and expects 404), or
in `PUBLIC_ROUTES` with the reason it is not couple-scoped. A new route in neither list fails the
architecture test, so no endpoint can skip the check. Each content module adds its factories (F3+).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from django.urls import URLPattern, URLResolver, get_resolver


@dataclass(frozen=True, slots=True)
class Route:
    name: str
    path: str
    parameters: tuple[str, ...]
    callback: Any


@dataclass(frozen=True, slots=True)
class ResourceFactory:
    """`create(couple, author)` stores a resource of `couple` and returns the URL kwargs addressing it."""

    create: Callable[[Any, Any], dict[str, str]]
    methods: tuple[str, ...]


FACTORIES: dict[str, ResourceFactory] = {}

PUBLIC_ROUTES: dict[str, str] = {
    "identity_get_invite": "anonymous; addressed by a secret invite token, not by a couple-owned ID (ADR-004 §5)",
    "identity_accept_invite": "anonymous; addressed by a secret invite token, not by a couple-owned ID (ADR-004 §5)",
}


def _walk(patterns: list[Any], prefix: str = "") -> Iterator[Route]:
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _walk(entry.url_patterns, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern):
            converters = getattr(entry.pattern, "converters", {})
            yield Route(entry.name or "", prefix + str(entry.pattern), tuple(converters), entry.callback)


def api_routes() -> list[Route]:
    return [route for route in _walk(get_resolver().url_patterns) if route.path.startswith("api/v1/")]

"""Scoped throttles on Redis with an explicit outage policy (ADR-004 §4, ADR-011 §2, REQ-N-SEC-04).

Auth throttles (login, password recovery, invite accept) **fail closed**: if Redis is down they answer 503
`service_unavailable`, because brute force must not become possible when the counter store is unreachable.
Every other throttle **fails open**: a warning is logged and the request goes through. Catching the cache
error here is an adapter boundary (ADR-010 §3).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import redis
from rest_framework.request import Request
from rest_framework.throttling import ScopedRateThrottle

from cherrylove.shared.domain.errors import ServiceUnavailable

logger = logging.getLogger("cherrylove.throttling")


class FailClosedScopedThrottle(ScopedRateThrottle):
    def allow_request(self, request: Request, view: Any) -> bool:
        try:
            return super().allow_request(request, view)
        except redis.RedisError as error:
            raise ServiceUnavailable("throttle store unavailable") from error


class FailOpenScopedThrottle(ScopedRateThrottle):
    def allow_request(self, request: Request, view: Any) -> bool:
        try:
            return super().allow_request(request, view)
        except redis.RedisError as error:
            logger.warning("throttle store unavailable, allowing (fail open)", extra={"error": type(error).__name__})
            return True


class IpAndEmailThrottle(FailClosedScopedThrottle):
    """Counts per IP **and** submitted email; the email is hashed so Redis keys hold no address."""

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        email = request.data.get("email", "") if hasattr(request.data, "get") else ""
        digest = hashlib.sha256(str(email).strip().lower().encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": f"{self.get_ident(request)}:{digest}"}

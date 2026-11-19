"""Redis adapter of the Cache port, failing open (ADR-011 §1-2).

On any Redis error the value is computed from the source of truth and a warning is logged: slower, still
correct. Short socket timeouts keep a dead Redis from adding seconds to every request.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import cast

import redis

from cherrylove.shared.application.cache import Cacheable, effective_ttl

logger = logging.getLogger("cherrylove.cache")

SOCKET_TIMEOUT_SECONDS = 0.25


def redis_client(url: str) -> redis.Redis:
    return redis.Redis.from_url(
        url, socket_timeout=SOCKET_TIMEOUT_SECONDS, socket_connect_timeout=SOCKET_TIMEOUT_SECONDS
    )


class RedisCache:
    def __init__(self, client: redis.Redis, prefix: str = "cl:") -> None:
        self._client = client
        self._prefix = prefix

    def get_or_compute[T: Cacheable](self, key: str, compute: Callable[[], T], ttl: timedelta | None = None) -> T:
        full_key = self._prefix + key
        try:
            raw = self._client.get(full_key)
        except redis.RedisError as error:
            logger.warning(
                "cache read failed, computing (fail open)", extra={"key": key, "error": type(error).__name__}
            )
            return compute()
        if raw is not None:
            return cast("T", json.loads(raw))
        value = compute()
        try:
            self._client.set(full_key, json.dumps(value), ex=effective_ttl(ttl))
        except redis.RedisError as error:
            logger.warning("cache write failed (fail open)", extra={"key": key, "error": type(error).__name__})
        return value

    def delete(self, key: str) -> None:
        try:
            self._client.delete(self._prefix + key)
        except redis.RedisError as error:
            # The TTL bounds staleness; the actor cache TTL equals the access-token lifetime (ADR-011 §1).
            logger.warning("cache delete failed (fail open)", extra={"key": key, "error": type(error).__name__})

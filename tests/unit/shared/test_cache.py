"""Cache port semantics without Redis (IMPL-API-001 F1.14, ADR-011 §1-2)."""

from __future__ import annotations

import logging
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
import redis

from cherrylove.shared.application.cache import SAFETY_TTL, effective_ttl
from cherrylove.shared.infrastructure.redis_cache import RedisCache
from tests.fakes.cache import InMemoryCache


@pytest.mark.req("REQ-N-PERF-04")
@pytest.mark.parametrize(
    ("ttl", "expected"),
    [(None, SAFETY_TTL), (timedelta(minutes=10), timedelta(minutes=10)), (timedelta(days=2), SAFETY_TTL)],
)
def test_ttl_never_exceeds_24_hours(ttl: timedelta | None, expected: timedelta) -> None:
    assert effective_ttl(ttl) == expected


@pytest.mark.req("REQ-N-PERF-04")
def test_fake_caches_and_fails_open() -> None:
    cache = InMemoryCache()
    assert cache.get_or_compute("k", lambda: [1]) == [1]
    assert cache.get_or_compute("k", lambda: [2]) == [1]
    cache.down = True
    assert cache.get_or_compute("k", lambda: [3]) == [3]
    assert cache.computed == 2


@pytest.mark.req("REQ-N-PERF-04")
def test_a_failing_write_still_returns_the_value(caplog: pytest.LogCaptureFixture) -> None:
    client = MagicMock(spec=redis.Redis)
    client.get.return_value = None
    client.set.side_effect = redis.ConnectionError("down")
    with caplog.at_level(logging.WARNING, logger="cherrylove.cache"):
        assert RedisCache(client).get_or_compute("k", lambda: "v") == "v"
    assert caplog.records[0].message == "cache write failed (fail open)"
    client.set.assert_called_once_with("cl:k", '"v"', ex=SAFETY_TTL)

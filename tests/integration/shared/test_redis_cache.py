"""Cache port on real Redis, failing open (IMPL-API-001 F1.14, ADR-011 §1-2, REQ-N-PERF-04)."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

import pytest
from django.conf import settings

from cherrylove.shared.application.cache import Cache
from cherrylove.shared.infrastructure.redis_cache import RedisCache, redis_client

pytestmark = pytest.mark.integration


def _key() -> str:
    return f"test:{uuid.uuid4().hex}"


class Counter:
    def __init__(self, value: list[str]) -> None:
        self.value = value
        self.calls = 0

    def __call__(self) -> list[str]:
        self.calls += 1
        return self.value


@pytest.mark.req("REQ-N-PERF-04")
def test_miss_computes_then_hit_reads_the_cache() -> None:
    cache: Cache = RedisCache(redis_client(settings.REDIS_URL))
    key, compute = _key(), Counter(["card-1", "card-2"])
    assert cache.get_or_compute(key, compute) == ["card-1", "card-2"]
    assert cache.get_or_compute(key, compute) == ["card-1", "card-2"]
    assert compute.calls == 1
    cache.delete(key)
    assert cache.get_or_compute(key, compute) == ["card-1", "card-2"]
    assert compute.calls == 2


@pytest.mark.req("REQ-N-PERF-04")
@pytest.mark.parametrize(
    ("ttl", "maximum"), [(None, 86_400), (timedelta(minutes=10), 600), (timedelta(days=7), 86_400)]
)
def test_every_key_expires_within_24_hours(ttl: timedelta | None, maximum: int) -> None:
    client = redis_client(settings.REDIS_URL)
    key = _key()
    RedisCache(client).get_or_compute(key, lambda: 1, ttl=ttl)
    remaining = int(client.ttl(f"cl:{key}"))
    assert 0 < remaining <= maximum


@pytest.mark.req("REQ-N-PERF-04")
def test_unreachable_redis_computes_and_logs_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    cache = RedisCache(redis_client("redis://127.0.0.1:1/0"))
    compute = Counter(["computed"])
    with caplog.at_level(logging.WARNING, logger="cherrylove.cache"):
        assert cache.get_or_compute(_key(), compute) == ["computed"]
        cache.delete(_key())
    assert compute.calls == 1
    assert [record.message for record in caplog.records] == [
        "cache read failed, computing (fail open)",
        "cache delete failed (fail open)",
    ]

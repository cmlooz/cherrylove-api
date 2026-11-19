"""Job retry backoff (IMPL-API-001 F1.17, ADR-013 §2): 1 min → 4 h, at most 6 attempts."""

from __future__ import annotations

from datetime import timedelta

import pytest

from cherrylove.shared.application.retry_policy import MAX_ATTEMPTS, delay_after
from tests.fakes.clock import DEFAULT_NOW, FixedClock


@pytest.mark.req("REQ-N-ARC-01")
def test_delays_grow_from_one_minute_to_four_hours() -> None:
    delays = [delay_after(attempt) for attempt in range(1, MAX_ATTEMPTS)]
    assert delays == [timedelta(minutes=m) for m in (1, 4, 16, 64, 240)]


@pytest.mark.req("REQ-N-ARC-01")
def test_the_sixth_failure_is_final() -> None:
    assert MAX_ATTEMPTS == 6
    assert delay_after(6) is None
    assert delay_after(7) is None


@pytest.mark.req("REQ-N-ARC-01")
def test_attempts_start_at_one() -> None:
    with pytest.raises(ValueError, match="start at 1"):
        delay_after(0)


@pytest.mark.req("REQ-N-ARC-01")
def test_schedule_on_a_fixed_clock() -> None:
    clock, schedule = FixedClock(), []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        delay = delay_after(attempt)
        if delay is None:
            break
        clock.advance(delay)
        schedule.append(clock.now() - DEFAULT_NOW)
    assert schedule == [timedelta(minutes=m) for m in (1, 5, 21, 85, 325)]

"""Job retry policy (ADR-013 §2): exponential backoff from 1 minute to 4 hours, at most 6 attempts."""

from __future__ import annotations

from datetime import timedelta

MAX_ATTEMPTS = 6
FIRST_DELAY = timedelta(minutes=1)
FACTOR = 4
MAX_DELAY = timedelta(hours=4)


def delay_after(failed_attempt: int) -> timedelta | None:
    """Wait before the next attempt, or None when `failed_attempt` was the last one allowed."""
    if failed_attempt < 1:
        raise ValueError("attempts start at 1")
    if failed_attempt >= MAX_ATTEMPTS:
        return None
    multiplier: int = pow(FACTOR, failed_attempt - 1)
    return min(FIRST_DELAY * multiplier, MAX_DELAY)

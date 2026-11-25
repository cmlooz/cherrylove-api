"""Couple rules that need no storage (REQ-F-HOME-01, DEC-024)."""

from __future__ import annotations

from datetime import date


def days_together(relationship_start: date | None, today: date) -> int | None:
    """Civil days since the relationship start; `today` is the civil date in the couple's time zone."""
    if relationship_start is None:
        return None
    return max((today - relationship_start).days, 0)

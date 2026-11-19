"""Domain events (ADR-001 §3): facts other modules may react to, dispatched only after commit."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    """Base class. Events carry IDs and metadata only, never content (ADR-008, DEC-015)."""

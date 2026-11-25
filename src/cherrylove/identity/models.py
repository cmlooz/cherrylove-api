"""Django discovery shim (ADR-002 §1): the ORM models live in infrastructure."""

from __future__ import annotations

from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, User

__all__ = ["Couple", "CoupleMembership", "User"]

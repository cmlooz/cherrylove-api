"""Django discovery shim (ADR-002 §1): the ORM models live in infrastructure."""

from __future__ import annotations

from cherrylove.shared.infrastructure.orm import CoupleDataKey, JobExecution

__all__ = ["CoupleDataKey", "JobExecution"]

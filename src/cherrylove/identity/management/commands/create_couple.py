"""Django discovery shim: the command lives in identity.interfaces (ADR-002 §1)."""

from __future__ import annotations

from cherrylove.identity.interfaces.cli import CreateCoupleCommand as Command

__all__ = ["Command"]

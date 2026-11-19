"""In-memory Cache with the port's semantics (ADR-011 §1), including a switch to simulate an outage."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import cast

from cherrylove.shared.application.cache import Cacheable, effective_ttl


@dataclass
class InMemoryCache:
    values: dict[str, str] = field(default_factory=dict)
    ttls: dict[str, timedelta] = field(default_factory=dict)
    down: bool = False
    computed: int = 0

    def get_or_compute[T: Cacheable](self, key: str, compute: Callable[[], T], ttl: timedelta | None = None) -> T:
        if not self.down and key in self.values:
            return cast("T", json.loads(self.values[key]))
        self.computed += 1
        value = compute()
        if not self.down:
            self.values[key] = json.dumps(value)
            self.ttls[key] = effective_ttl(ttl)
        return value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)

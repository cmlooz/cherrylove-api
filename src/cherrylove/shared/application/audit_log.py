"""AuditLog port and diff-without-content (ADR-008 §2-3, REQ-F-LOG-01/02).

Each module classifies every field of an audited entity as **loggable** (value kept in the diff) or
**content** (only `{"changed": true}`). Registering an entity with an unclassified field fails at import
time; diffing an unclassified field fails too, so content can never slip into the log by omission.
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal, Protocol

from cherrylove.shared.domain.actor import Actor

type ActorType = Literal["partner", "staff", "system", "anonymous"]
type Outcome = Literal["success", "rejected", "failed"]


class UnclassifiedFieldError(LookupError):
    """An audited entity has a field that is neither loggable nor content (ADR-008 §2)."""


@dataclass(frozen=True, slots=True)
class FieldClassification:
    entity_type: str
    loggable: frozenset[str]
    content: frozenset[str]


_REGISTRY: dict[str, FieldClassification] = {}


def classify(entity_type: str, entity: type, *, loggable: set[str], content: set[str]) -> FieldClassification:
    """Register an audited entity; its dataclass fields must be exactly `loggable | content`."""
    if loggable & content:
        raise UnclassifiedFieldError(f"{entity_type}: {sorted(loggable & content)} are both loggable and content")
    declared = {f.name for f in dataclasses.fields(entity)}
    if declared != loggable | content:
        missing, unknown = declared - loggable - content, (loggable | content) - declared
        raise UnclassifiedFieldError(f"{entity_type}: unclassified {sorted(missing)}, unknown {sorted(unknown)}")
    classification = FieldClassification(entity_type, frozenset(loggable), frozenset(content))
    _REGISTRY[entity_type] = classification
    return classification


def registered() -> Mapping[str, FieldClassification]:
    return dict(_REGISTRY)


def _jsonable(value: object) -> object:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "value") and isinstance(value.value, uuid.UUID):  # typed IDs (Uuid7 subclasses)
        return str(value.value)
    return value


def diff(
    classification: FieldClassification, before: Mapping[str, object] | None, after: Mapping[str, object]
) -> dict[str, object]:
    """Changed fields only; `before=None` is a creation."""
    changes: dict[str, object] = {}
    previous = before or {}
    for name in sorted(set(previous) | set(after)):
        if name not in classification.loggable and name not in classification.content:
            raise UnclassifiedFieldError(f"{classification.entity_type}.{name}")
        old, new = previous.get(name), after.get(name)
        if before is not None and old == new:
            continue
        if before is None and new is None:
            continue
        if name in classification.content:
            changes[name] = {"changed": True}
        else:
            changes[name] = {"from": _jsonable(old), "to": _jsonable(new)}
    return changes


def email_fingerprint(email: str, key: str) -> str:
    """HMAC-SHA256 of the normalized email: correlates failed logins without storing who typed what."""
    return hmac.new(key.encode(), email.strip().lower().encode(), hashlib.sha256).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class AuditEvent:
    action: str
    outcome: Outcome = "success"
    actor: Actor | None = None
    actor_type: ActorType | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    changes: Mapping[str, object] = field(default_factory=dict)
    ip: str | None = None
    device: Mapping[str, object] = field(default_factory=dict)

    @property
    def resolved_actor_type(self) -> ActorType:
        if self.actor_type is not None:
            return self.actor_type
        return "partner" if self.actor is not None else "anonymous"


class AuditLog(Protocol):
    def record(self, event: AuditEvent) -> None:
        """Inside the use-case transaction: the event commits or rolls back with the change (ADR-001 §4)."""
        ...

    def record_rejected(self, event: AuditEvent) -> None:
        """After the rollback, in its own autocommit write, so the attempt survives (ADR-008 §3)."""
        ...

"""Edit my account and change my password (REQ-F-ACC-01…04; ADR-004 §3, DEC-025, DEC-051).

Name, language and avatar are editable; the birth date is corrected only by an admin (DEC-025). Media arrive
in F4, so until then no avatar id can be valid: any non-null id is `invalid_media` and `null` clears it.
A language change drops the cached Actor after commit, since the Actor carries the locale (ADR-005).

Changing the password needs the current one and revokes every session except the current one, named by
the access token's `sid` (DEC-051). A token without `sid` (issued before DEC-051) revokes them all.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from cherrylove.identity.application.ports import ActorCache, SessionStore
from cherrylove.shared.application.audit_log import AuditEvent, AuditLog
from cherrylove.shared.application.unit_of_work import UnitOfWork
from cherrylove.shared.domain.actor import Actor, Locale
from cherrylove.shared.domain.errors import FieldError
from cherrylove.shared.domain.ids import UserId

UNSET = object()


@dataclass(frozen=True, slots=True)
class ProfileChanges:
    name: str | None = None
    language: Locale | None = None
    avatar_media_id: uuid.UUID | object | None = UNSET


@dataclass(frozen=True, slots=True)
class ProfileBefore:
    name: str
    language: str
    avatar_media_id: uuid.UUID | None


class Profiles(Protocol):
    def lock(self, user_id: UserId) -> ProfileBefore: ...

    def save(self, user_id: UserId, name: str, language: str, avatar_media_id: uuid.UUID | None) -> None:
        """Store the profile and bump the user's version."""
        ...


class Passwords(Protocol):
    def matches(self, user_id: UserId, password: str) -> bool: ...

    def set(self, user_id: UserId, password: str) -> None:
        """Validate (FieldError on `/new_password`) and store the new password."""
        ...


@dataclass(frozen=True, slots=True)
class UpdateMe:
    uow: UnitOfWork
    profiles: Profiles
    actors: ActorCache
    audit: AuditLog

    def execute(self, actor: Actor, changes: ProfileChanges) -> None:
        avatar = changes.avatar_media_id
        if avatar is not UNSET and avatar is not None:
            raise FieldError("/avatar_media_id", "invalid_media")
        with self.uow.atomic():
            before = self.profiles.lock(actor.user_id)
            name = changes.name if changes.name is not None else before.name
            language = changes.language if changes.language is not None else before.language
            avatar_id = before.avatar_media_id if avatar is UNSET else None
            diff: dict[str, object] = {}
            if name != before.name:
                diff["name"] = {"changed": True}  # personal data stays out of the audit (ADR-008 §2)
            if language != before.language:
                diff["language"] = {"from": before.language, "to": language}
            if avatar_id != before.avatar_media_id:
                diff["avatar_media_id"] = {"changed": True}
            if not diff:
                return
            self.profiles.save(actor.user_id, name, language, avatar_id)
            self.audit.record(
                AuditEvent(
                    action="account.updated",
                    actor=actor,
                    entity_type="user",
                    entity_id=actor.user_id.value,
                    changes=diff,
                )
            )
            if "language" in diff:
                self.uow.on_commit(lambda: self.actors.forget(actor.user_id))


@dataclass(frozen=True, slots=True)
class ChangePassword:
    uow: UnitOfWork
    passwords: Passwords
    sessions: SessionStore
    audit: AuditLog

    def execute(self, actor: Actor, session_id: str | None, current: str, new: str) -> None:
        if not self.passwords.matches(actor.user_id, current):
            raise FieldError("/current_password", "incorrect_password")
        with self.uow.atomic():
            self.passwords.set(actor.user_id, new)
            if session_id is None:
                revoked = self.sessions.revoke_all(actor.user_id)
            else:
                revoked = self.sessions.revoke_others(actor.user_id, session_id)
            self.audit.record(
                AuditEvent(
                    action="auth.password_changed",
                    actor=actor,
                    entity_type="user",
                    entity_id=actor.user_id.value,
                    changes={"password": {"changed": True}, "revoked_sessions": {"from": None, "to": revoked}},
                )
            )

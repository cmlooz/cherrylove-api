"""Deactivate a user (REQ-F-ADM-01, REQ-F-AUTH-09; ADR-005 consequence, ADR-004 §3).

The account is disabled and every refresh token revoked in one audited transaction. The cached Actor is
dropped **after** the commit: dropped earlier, a concurrent request could cache the still-committed active
state again for 10 minutes. With the key gone, the next request carrying a still-valid access token resolves
from the database and is refused at once. F9.2 (staff admin) and F9.4 (archive couple) reuse this.
"""

from __future__ import annotations

from dataclasses import dataclass

from cherrylove.identity.application.ports import AccountStatus, ActorCache, SessionStore
from cherrylove.shared.application.audit_log import ActorType, AuditEvent, AuditLog
from cherrylove.shared.application.unit_of_work import UnitOfWork
from cherrylove.shared.domain.errors import NotFound
from cherrylove.shared.domain.ids import UserId


@dataclass(frozen=True, slots=True)
class DeactivateUser:
    uow: UnitOfWork
    accounts: AccountStatus
    sessions: SessionStore
    actors: ActorCache
    audit: AuditLog

    def execute(self, user_id: UserId, *, actor_type: ActorType = "system") -> None:
        with self.uow.atomic():
            was_active = self.accounts.deactivate(user_id)
            if was_active is None:
                raise NotFound("no such user")
            revoked = self.sessions.revoke_all(user_id)
            self.audit.record(
                AuditEvent(
                    action="admin.user_deactivated",
                    actor_type=actor_type,
                    entity_type="user",
                    entity_id=user_id.value,
                    changes={
                        "is_active": {"from": was_active, "to": False},
                        "revoked_sessions": {"from": None, "to": revoked},
                    },
                )
            )
            self.uow.on_commit(lambda: self.actors.forget(user_id))

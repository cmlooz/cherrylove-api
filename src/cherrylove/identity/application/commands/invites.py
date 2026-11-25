"""Issue, resend and revoke invites (REQ-F-AUTH-02, REQ-F-ADM-02, DEC-017; ADR-004 §4).

`IssueInviteToken` runs inside the send-email job: it creates the token, stores only its SHA-256 and returns the
raw value for the email link. `ResendInvite` revokes the seat's live invite and creates a new one with a new
token and a fresh 72 h; `RevokeInvite` kills a pending invite.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from cherrylove.identity.application.commands.create_couple import SEND_INVITE_EMAIL
from cherrylove.identity.application.ports import InviteRepository, TokenGenerator
from cherrylove.identity.domain.invite import Slot, invite_expires_at
from cherrylove.identity.domain.invite_token import hash_token
from cherrylove.shared.application.audit_log import AuditEvent, AuditLog
from cherrylove.shared.application.job_queue import JobQueue
from cherrylove.shared.application.unit_of_work import UnitOfWork
from cherrylove.shared.domain.clock import Clock
from cherrylove.shared.domain.errors import NotFound
from cherrylove.shared.domain.ids import CoupleId, IdGenerator


@dataclass(frozen=True, slots=True)
class IssueInviteToken:
    invites: InviteRepository
    tokens: TokenGenerator
    clock: Clock

    def execute(self, invite_id: uuid.UUID) -> str:
        invite = self.invites.get(invite_id)
        if invite is None or invite.status != "pending":
            raise NotFound("no pending invite")
        raw = self.tokens.new()
        self.invites.set_token(invite_id, hash_token(raw), self.clock.now())
        return raw


@dataclass(frozen=True, slots=True)
class ResendInvite:
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator
    invites: InviteRepository
    jobs: JobQueue
    audit: AuditLog

    def execute(self, couple_id: CoupleId, slot: Slot) -> uuid.UUID:
        current = self.invites.pending_for_seat(couple_id, slot)
        if current is None:
            raise NotFound("no pending invite for this seat")
        new_id = self.ids.new()
        with self.uow.atomic():
            self.invites.revoke(current.invite_id)
            self.invites.add_pending(new_id, couple_id, slot, current.email, invite_expires_at(self.clock.now()))
            self.jobs.enqueue(SEND_INVITE_EMAIL, {"invite_id": str(new_id)}, idempotency_key=f"email:invite:{new_id}")
            self.audit.record(
                AuditEvent(
                    action="invite.resent",
                    actor_type="system",
                    entity_type="invite",
                    entity_id=new_id,
                    changes={"replaces": {"from": None, "to": str(current.invite_id)}},
                )
            )
        return new_id


@dataclass(frozen=True, slots=True)
class RevokeInvite:
    uow: UnitOfWork
    invites: InviteRepository
    audit: AuditLog

    def execute(self, invite_id: uuid.UUID) -> None:
        invite = self.invites.get(invite_id)
        if invite is None or invite.status != "pending":
            raise NotFound("no pending invite")
        with self.uow.atomic():
            self.invites.revoke(invite_id)
            self.audit.record(
                AuditEvent(action="invite.revoked", actor_type="system", entity_type="invite", entity_id=invite_id)
            )

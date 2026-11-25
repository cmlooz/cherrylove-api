"""Create a couple with two invites (REQ-F-AUTH-01, REQ-F-AUTH-10, REQ-F-ADM-01; DEC-028).

One transaction: couple, sync_state and data key (provisioners), two pending invites, one invite-email job
per invite, and the `admin.couple_created` audit event. Run as the `system` actor until F9 gives staff a UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from cherrylove.identity.application.ports import CoupleProvisioner, CoupleRepository, InviteRepository, MembershipQuery
from cherrylove.identity.domain.errors import EmailAlreadyInCouple
from cherrylove.identity.domain.invite import Slot, invite_expires_at, normalize_email
from cherrylove.shared.application.audit_log import AuditEvent, AuditLog
from cherrylove.shared.application.job_queue import JobQueue
from cherrylove.shared.application.unit_of_work import UnitOfWork
from cherrylove.shared.domain.clock import Clock
from cherrylove.shared.domain.errors import FieldError
from cherrylove.shared.domain.ids import CoupleId, IdGenerator

SEND_INVITE_EMAIL = "identity.send_invite_email"


@dataclass(frozen=True, slots=True)
class CreateCouple:
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator
    memberships: MembershipQuery
    couples: CoupleRepository
    invites: InviteRepository
    provisioners: tuple[CoupleProvisioner, ...]
    jobs: JobQueue
    audit: AuditLog

    def execute(self, first_email: str, second_email: str) -> CoupleId:
        emails = (normalize_email(first_email), normalize_email(second_email))
        if emails[0] == emails[1]:
            raise FieldError("/emails/1", "invalid_format", detail="the two partners need different emails")
        if self.memberships.emails_in_a_couple(emails):
            raise EmailAlreadyInCouple("an email already belongs to a couple")

        couple_id = CoupleId(self.ids.new())
        now = self.clock.now()
        with self.uow.atomic():
            self.couples.add(couple_id)
            for provisioner in self.provisioners:
                provisioner.provision(couple_id)
            slots: tuple[Slot, Slot] = (1, 2)
            for slot, email in zip(slots, emails, strict=True):
                invite_id = self.ids.new()
                self.invites.add_pending(invite_id, couple_id, slot, email, invite_expires_at(now))
                self.jobs.enqueue(
                    SEND_INVITE_EMAIL, {"invite_id": str(invite_id)}, idempotency_key=f"email:invite:{invite_id}"
                )
            self.audit.record(
                AuditEvent(
                    action="admin.couple_created",
                    actor_type="system",
                    entity_type="couple",
                    entity_id=couple_id.value,
                    changes={"invites": {"from": None, "to": 2}},
                )
            )
        return couple_id

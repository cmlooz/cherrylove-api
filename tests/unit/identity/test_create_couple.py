"""Create couple use case with fakes (IMPL-API-001 F2.5; REQ-F-AUTH-01, REQ-F-AUTH-10, REQ-F-ADM-01)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from cherrylove.identity.application.commands.create_couple import SEND_INVITE_EMAIL, CreateCouple
from cherrylove.identity.domain.errors import EmailAlreadyInCouple
from cherrylove.shared.domain.errors import FieldError
from tests.fakes.audit_log import InMemoryAuditLog
from tests.fakes.clock import FixedClock, SequentialIdGenerator
from tests.fakes.identity import InMemoryCouples, InMemoryInvites, InMemoryMemberships, RecordingProvisioner
from tests.fakes.job_queue import InMemoryJobQueue
from tests.fakes.unit_of_work import InMemoryUnitOfWork


class World:
    def __init__(self, members: set[str] | None = None) -> None:
        self.clock = FixedClock()
        self.uow = InMemoryUnitOfWork()
        self.couples, self.invites = InMemoryCouples(), InMemoryInvites()
        self.sync, self.keys = RecordingProvisioner(), RecordingProvisioner()
        self.jobs, self.audit = InMemoryJobQueue(), InMemoryAuditLog()
        self.use_case = CreateCouple(
            uow=self.uow,
            clock=self.clock,
            ids=SequentialIdGenerator(self.clock),
            memberships=InMemoryMemberships(members or set()),
            couples=self.couples,
            invites=self.invites,
            provisioners=(self.sync, self.keys),
            jobs=self.jobs,
            audit=self.audit,
        )


@pytest.mark.req("REQ-F-AUTH-01")
def test_creates_couple_provisioning_invites_jobs_and_audit_in_one_transaction() -> None:
    world = World()
    couple_id = world.use_case.execute(" Camila@Example.com ", "andres@example.com")

    assert world.couples.added == [couple_id]
    assert world.sync.provisioned == [couple_id]
    assert world.keys.provisioned == [couple_id]
    assert [(i.slot, i.email) for i in world.invites.pending] == [(1, "camila@example.com"), (2, "andres@example.com")]
    assert {i.expires_at - world.clock.now() for i in world.invites.pending} == {timedelta(hours=72)}
    assert [(j.job, j.idempotency_key) for j in world.jobs.jobs] == [
        (SEND_INVITE_EMAIL, f"email:invite:{i.invite_id}") for i in world.invites.pending
    ]
    [event] = world.audit.events
    assert (event.action, event.resolved_actor_type, event.entity_id) == (
        "admin.couple_created",
        "system",
        couple_id.value,
    )
    assert (world.uow.commits, world.uow.rollbacks) == (1, 0)


@pytest.mark.req("REQ-F-AUTH-10")
def test_an_email_already_in_a_couple_is_refused_before_anything_is_written() -> None:
    world = World(members={"camila@example.com"})
    with pytest.raises(EmailAlreadyInCouple) as error:
        world.use_case.execute("CAMILA@example.com", "andres@example.com")
    assert (error.value.code, error.value.status) == ("email_already_in_couple", 409)
    assert world.couples.added == []
    assert world.invites.pending == []
    assert world.jobs.jobs == []
    assert world.audit.events == []


@pytest.mark.req("REQ-F-AUTH-01")
def test_the_two_partners_need_different_emails() -> None:
    world = World()
    with pytest.raises(FieldError) as error:
        world.use_case.execute("same@example.com", " SAME@example.com")
    assert (error.value.pointer, error.value.field_code) == ("/emails/1", "invalid_format")
    assert world.couples.added == []

"""Composition root of the identity module (ADR-002 §1): plain constructors, no DI library."""

from __future__ import annotations

from cherrylove.audit.application.public import audit_log
from cherrylove.identity.application.commands.create_couple import CreateCouple
from cherrylove.identity.infrastructure.adapters.provisioning import CoupleDataKeyProvisioner, SyncStateViaFacade
from cherrylove.identity.infrastructure.repositories import (
    DjangoCoupleRepository,
    DjangoInviteRepository,
    DjangoMembershipQuery,
)
from cherrylove.shared.infrastructure.clock import SystemClock, Uuid7Generator
from cherrylove.shared.infrastructure.django_job_queue import DjangoJobQueue
from cherrylove.shared.infrastructure.django_unit_of_work import DjangoUnitOfWork


def create_couple() -> CreateCouple:
    return CreateCouple(
        uow=DjangoUnitOfWork(),
        clock=SystemClock(),
        ids=Uuid7Generator(),
        memberships=DjangoMembershipQuery(),
        couples=DjangoCoupleRepository(),
        invites=DjangoInviteRepository(),
        provisioners=(SyncStateViaFacade(), CoupleDataKeyProvisioner()),
        jobs=DjangoJobQueue(),
        audit=audit_log(),
    )

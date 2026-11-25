"""Composition root of the identity module (ADR-002 §1): plain constructors, no DI library."""

from __future__ import annotations

from django.conf import settings

from cherrylove.audit.application.public import audit_log
from cherrylove.identity.application.commands.create_couple import CreateCouple
from cherrylove.identity.application.commands.invites import IssueInviteToken
from cherrylove.identity.application.commands.send_invite_email import SendInviteEmail
from cherrylove.identity.infrastructure.adapters.mailer import DjangoInviteMailer
from cherrylove.identity.infrastructure.adapters.provisioning import CoupleDataKeyProvisioner, SyncStateViaFacade
from cherrylove.identity.infrastructure.adapters.tokens import SecretsTokenGenerator
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


def send_invite_email() -> SendInviteEmail:
    invites, clock = DjangoInviteRepository(), SystemClock()
    return SendInviteEmail(
        invites=invites,
        issue=IssueInviteToken(invites, SecretsTokenGenerator(), clock),
        mailer=DjangoInviteMailer(),
        clock=clock,
        link_template=settings.INVITE_LINK_TEMPLATE,
    )

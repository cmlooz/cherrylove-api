"""Composition root of the identity module (ADR-002 §1): plain constructors, no DI library."""

from __future__ import annotations

from django.conf import settings

from cherrylove.audit.application.public import audit_log
from cherrylove.identity.application.commands.create_couple import CreateCouple
from cherrylove.identity.application.commands.invites import IssueInviteToken
from cherrylove.identity.application.commands.onboarding import AcceptInvite, GetInvite
from cherrylove.identity.application.commands.send_invite_email import SendInviteEmail
from cherrylove.identity.application.commands.sessions import Login, Logout, RefreshSession
from cherrylove.identity.infrastructure.adapters.jwt_tokens import JwtSessionStore, JwtTokenIssuer
from cherrylove.identity.infrastructure.adapters.mailer import DjangoInviteMailer
from cherrylove.identity.infrastructure.adapters.provisioning import CoupleDataKeyProvisioner, SyncStateViaFacade
from cherrylove.identity.infrastructure.adapters.tokens import SecretsTokenGenerator
from cherrylove.identity.infrastructure.repositories import (
    DjangoCoupleRepository,
    DjangoCredentialCheck,
    DjangoInviteLookup,
    DjangoInviteRepository,
    DjangoMembershipQuery,
    DjangoPartnerRepository,
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


def get_invite() -> GetInvite:
    return GetInvite(DjangoInviteLookup(), SystemClock())


def accept_invite() -> AcceptInvite:
    return AcceptInvite(
        uow=DjangoUnitOfWork(),
        clock=SystemClock(),
        ids=Uuid7Generator(),
        lookup=DjangoInviteLookup(),
        partners=DjangoPartnerRepository(),
        sessions=JwtTokenIssuer(),
        audit=audit_log(),
    )


def login() -> Login:
    return Login(DjangoUnitOfWork(), DjangoCredentialCheck(), JwtTokenIssuer(), audit_log(), settings.AUDIT_HMAC_KEY)


def refresh_session() -> RefreshSession:
    return RefreshSession(DjangoUnitOfWork(), JwtSessionStore(), audit_log())


def logout() -> Logout:
    return Logout(DjangoUnitOfWork(), JwtSessionStore(), audit_log())

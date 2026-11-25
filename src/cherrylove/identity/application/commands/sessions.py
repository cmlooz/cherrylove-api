"""Log in, refresh and log out (REQ-F-AUTH-07, REQ-F-ACC-06, REQ-N-SEC-03; ADR-004 §2-3, §6).

Every attempt is audited. A failed login stores the HMAC of the email under AUDIT_HMAC_KEY, never the email
or the password (ADR-008 §2). An archived couple can authenticate but gets `couple_archived`, so the app can
explain why (REQ-F-AUTH-09).
"""

from __future__ import annotations

from dataclasses import dataclass

from cherrylove.identity.application.ports import CredentialCheck, Session, SessionStore, TokenIssuer
from cherrylove.identity.domain.errors import CoupleArchived, InvalidCredentials
from cherrylove.identity.domain.invite import normalize_email
from cherrylove.shared.application.audit_log import AuditEvent, AuditLog, email_fingerprint
from cherrylove.shared.application.unit_of_work import UnitOfWork
from cherrylove.shared.domain.errors import NotAuthenticated
from cherrylove.shared.domain.ids import UserId


@dataclass(frozen=True, slots=True)
class RequestInfo:
    ip: str | None
    client: str


def _device(info: RequestInfo) -> dict[str, object]:
    return {"client": info.client}


@dataclass(frozen=True, slots=True)
class Login:
    uow: UnitOfWork
    credentials: CredentialCheck
    sessions: TokenIssuer
    audit: AuditLog
    hmac_key: str

    def execute(self, email: str, password: str, info: RequestInfo) -> Session:
        account = self.credentials.verify(normalize_email(email), password)
        if account is None:
            fingerprint = email_fingerprint(email, self.hmac_key)
            self.audit.record_rejected(
                AuditEvent(
                    action="auth.login_failed",
                    outcome="rejected",
                    actor_type="anonymous",
                    changes={"email_hmac": {"from": None, "to": fingerprint}},
                    ip=info.ip,
                    device=_device(info),
                )
            )
            raise InvalidCredentials("wrong email or password")
        if account.couple_archived:
            self.audit.record_rejected(
                AuditEvent(
                    action="auth.login_failed",
                    outcome="rejected",
                    actor_type="partner",
                    entity_type="user",
                    entity_id=account.user_id.value,
                    changes={"reason": {"from": None, "to": "couple_archived"}},
                    ip=info.ip,
                    device=_device(info),
                )
            )
            raise CoupleArchived("the couple is archived")
        with self.uow.atomic():
            session = self.sessions.issue(account.user_id)
            self.audit.record(
                AuditEvent(
                    action="auth.login",
                    actor_type="partner",
                    entity_type="user",
                    entity_id=account.user_id.value,
                    ip=info.ip,
                    device=_device(info),
                )
            )
        return session


@dataclass(frozen=True, slots=True)
class RefreshSession:
    uow: UnitOfWork
    store: SessionStore
    audit: AuditLog

    def execute(self, refresh: str | None, info: RequestInfo) -> Session:
        if not refresh:
            raise NotAuthenticated("no refresh token")
        check = self.store.check(refresh)
        if check.kind == "reused" and check.user_id is not None:
            self._kill_all_sessions(check.user_id, info)
            raise NotAuthenticated("refresh token reused")
        if check.kind != "valid":
            raise NotAuthenticated("unusable refresh token")
        with self.uow.atomic():
            user_id, session = self.store.rotate(refresh)
            self.audit.record(
                AuditEvent(
                    action="auth.refreshed",
                    actor_type="partner",
                    entity_type="user",
                    entity_id=user_id.value,
                    ip=info.ip,
                    device=_device(info),
                )
            )
        return session

    def _kill_all_sessions(self, user_id: UserId, info: RequestInfo) -> None:
        """Theft response: committed before the 401 so the attacker's copy dies too (ADR-004 §3)."""
        with self.uow.atomic():
            revoked = self.store.revoke_all(user_id)
            self.audit.record(
                AuditEvent(
                    action="auth.refresh_reused",
                    outcome="rejected",
                    actor_type="partner",
                    entity_type="user",
                    entity_id=user_id.value,
                    changes={"revoked_sessions": {"from": None, "to": revoked}},
                    ip=info.ip,
                    device=_device(info),
                )
            )


@dataclass(frozen=True, slots=True)
class Logout:
    uow: UnitOfWork
    store: SessionStore
    audit: AuditLog

    def execute(self, refresh: str | None, info: RequestInfo) -> None:
        if not refresh:
            return
        with self.uow.atomic():
            user_id = self.store.revoke(refresh)
            if user_id is not None:
                self.audit.record(
                    AuditEvent(
                        action="auth.logout",
                        actor_type="partner",
                        entity_type="user",
                        entity_id=user_id.value,
                        ip=info.ip,
                        device=_device(info),
                    )
                )

"""Password recovery (REQ-F-AUTH-08; ADR-004 §4, ADR-010 §2 exception, ADR-012 §4).

Requesting answers the same whether or not the email exists; a mail is sent only for a real account, by a job
that issues the token at send time (Django's HMAC token: 30 min, dead after any password change). Confirming
sets the new password, kills every session of the account and is audited. A wrong, expired or used token is a
field error (`invalid_token`), never a hint about which part was wrong.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from cherrylove.identity.application.ports import RecoveryAccounts, RecoveryMailer, SessionStore
from cherrylove.identity.domain.invite import normalize_email
from cherrylove.shared.application.audit_log import AuditEvent, AuditLog, email_fingerprint
from cherrylove.shared.application.job_queue import JobQueue
from cherrylove.shared.application.unit_of_work import UnitOfWork
from cherrylove.shared.domain.errors import FieldError
from cherrylove.shared.domain.ids import IdGenerator

SEND_PASSWORD_RECOVERY = "identity.send_password_recovery"  # noqa: S105 - a job name, not a secret

SUBJECTS = {"es": "Recupera tu contraseña de CherryLove", "en": "Reset your CherryLove password"}
BODIES = {
    "es": """Hola, {name}:

Alguien pidió cambiar la contraseña de tu cuenta de CherryLove. Si fuiste tú, abre este enlace:

{link}

El enlace vence en 30 minutos y deja de funcionar si cambias la contraseña. Si no lo pediste, ignora este correo.
""",
    "en": """Hi {name},

Someone asked to change the password of your CherryLove account. If it was you, open this link:

{link}

The link expires in 30 minutes and stops working once the password changes. If you did not ask, ignore this email.
""",
}


@dataclass(frozen=True, slots=True)
class RequestPasswordRecovery:
    uow: UnitOfWork
    ids: IdGenerator
    accounts: RecoveryAccounts
    jobs: JobQueue
    audit: AuditLog
    hmac_key: str

    def execute(self, email: str) -> None:
        user_id = self.accounts.by_email(normalize_email(email))
        with self.uow.atomic():
            if user_id is not None:
                self.jobs.enqueue(
                    SEND_PASSWORD_RECOVERY,
                    {"user_id": str(user_id.value)},
                    idempotency_key=f"email:recovery:{self.ids.new()}",
                )
            self.audit.record(
                AuditEvent(
                    action="auth.password_recovery_requested",
                    actor_type="anonymous",
                    changes={"email_hmac": {"from": None, "to": email_fingerprint(email, self.hmac_key)}},
                )
            )


@dataclass(frozen=True, slots=True)
class SendPasswordRecovery:
    accounts: RecoveryAccounts
    mailer: RecoveryMailer
    link_template: str

    def execute(self, user_id: uuid.UUID) -> bool:
        recipient = self.accounts.recipient(user_id)
        if recipient is None:
            return False
        link = self.link_template.format(uid=recipient.uid, token=self.accounts.issue_token(user_id))
        language = recipient.language if recipient.language in BODIES else "es"
        self.mailer.send(recipient.email, SUBJECTS[language], BODIES[language].format(name=recipient.name, link=link))
        return True


@dataclass(frozen=True, slots=True)
class ConfirmPasswordRecovery:
    uow: UnitOfWork
    accounts: RecoveryAccounts
    sessions: SessionStore
    audit: AuditLog

    def execute(self, uid: str, token: str, new_password: str) -> None:
        user_id = self.accounts.check_token(uid, token)
        if user_id is None:
            raise FieldError("/token", "invalid_token")
        with self.uow.atomic():
            self.accounts.set_password(user_id, new_password)
            revoked = self.sessions.revoke_all(user_id)
            self.audit.record(
                AuditEvent(
                    action="auth.password_recovered",
                    actor_type="partner",
                    entity_type="user",
                    entity_id=user_id.value,
                    changes={"password": {"changed": True}, "revoked_sessions": {"from": None, "to": revoked}},
                )
            )

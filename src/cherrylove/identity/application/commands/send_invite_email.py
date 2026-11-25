"""Send the bilingual invite email (REQ-F-AUTH-01/02, ADR-012 §4, ADR-013 §2).

Runs inside the `identity.send_invite_email` job: issues the token (only its hash is stored), builds the link
and sends one email, Spanish first and then English, because the invitee has no language preference yet.
An invite that is no longer pending (revoked by a resend, accepted, expired) is skipped, not retried.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from cherrylove.identity.application.commands.invites import IssueInviteToken
from cherrylove.identity.application.ports import InviteMailer, InviteRepository
from cherrylove.shared.domain.clock import Clock

SUBJECT = "Tu invitación a CherryLove · Your CherryLove invitation"

BODY = """Hola:

Te invitaron a CherryLove, el espacio privado para los dos. Abre este enlace para crear tu cuenta:

{link}

El enlace vale una sola vez y vence en 72 horas. Si no esperabas esta invitación, ignora este correo.

---

Hi,

You have been invited to CherryLove, the private space for the two of you. Open this link to create your account:

{link}

The link works once and expires in 72 hours. If you did not expect this invitation, ignore this email.
"""


@dataclass(frozen=True, slots=True)
class SendInviteEmail:
    invites: InviteRepository
    issue: IssueInviteToken
    mailer: InviteMailer
    clock: Clock
    link_template: str

    def execute(self, invite_id: uuid.UUID) -> bool:
        """True when an email was sent; False when the invite is no longer usable."""
        invite = self.invites.get(invite_id)
        if invite is None or invite.status != "pending" or invite.expires_at <= self.clock.now():
            return False
        token = self.issue.execute(invite_id)
        self.mailer.send(invite.email, SUBJECT, BODY.format(link=self.link_template.format(token=token)))
        return True

"""Identity job handlers (ADR-013): registered at startup by IdentityConfig.ready()."""

from __future__ import annotations

from cherrylove.identity.application.commands.create_couple import SEND_INVITE_EMAIL
from cherrylove.shared.application.job_queue import Payload
from cherrylove.shared.infrastructure.django_job_queue import register_job


@register_job(SEND_INVITE_EMAIL)
def send_invite_email(payload: Payload) -> None:
    """Issues the invite token and sends the bilingual email: implemented by IMPL-API-001 F2.7."""
    raise NotImplementedError("IMPL-API-001 F2.7")

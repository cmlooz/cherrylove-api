"""Identity job handlers (ADR-013): registered at startup by IdentityConfig.ready()."""

from __future__ import annotations

import uuid

from cherrylove.identity import wiring
from cherrylove.identity.application.commands.create_couple import SEND_INVITE_EMAIL
from cherrylove.shared.application.job_queue import Payload
from cherrylove.shared.infrastructure.django_job_queue import register_job


@register_job(SEND_INVITE_EMAIL)
def send_invite_email(payload: Payload) -> None:
    wiring.send_invite_email().execute(uuid.UUID(str(payload["invite_id"])))

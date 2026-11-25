"""Email through Django's configured backend (SMTP; Mailpit locally, REQ-N-OPS-01)."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail


class DjangoInviteMailer:
    def send(self, to: str, subject: str, body: str) -> None:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)

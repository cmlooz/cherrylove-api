"""Password recovery on Django's token generator (ADR-004 §4): HMAC tokens, 30 min, dead after a password change."""

from __future__ import annotations

import uuid

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from cherrylove.identity.application.ports import RecoveryRecipient
from cherrylove.identity.infrastructure.orm import User
from cherrylove.shared.domain.errors import FieldError
from cherrylove.shared.domain.ids import UserId

DJANGO_TO_FIELD_CODE = {"password_too_short": "too_short"}


class DjangoRecoveryAccounts:
    def by_email(self, email: str) -> UserId | None:
        user = User.objects.filter(
            email=email, is_active=True, is_staff=False, is_superuser=False, membership__isnull=False
        ).first()
        return UserId(user.id) if user else None

    def recipient(self, user_id: uuid.UUID) -> RecoveryRecipient | None:
        user = User.objects.filter(id=user_id, is_active=True).first()
        if user is None:
            return None
        return RecoveryRecipient(urlsafe_base64_encode(force_bytes(user.pk)), user.email, user.name, user.language)

    def issue_token(self, user_id: uuid.UUID) -> str:
        return default_token_generator.make_token(User.objects.get(id=user_id))

    def check_token(self, uid: str, token: str) -> UserId | None:
        try:
            user_id = uuid.UUID(force_str(urlsafe_base64_decode(uid)))
        except ValueError:
            return None
        user = User.objects.filter(id=user_id, is_active=True).first()
        if user is None or not default_token_generator.check_token(user, token):
            return None
        return UserId(user.id)

    def set_password(self, user_id: UserId, password: str) -> None:
        user = User.objects.get(id=user_id.value)
        try:
            validate_password(password, user)
        except ValidationError as error:
            code = DJANGO_TO_FIELD_CODE.get(error.error_list[0].code or "", "invalid_format")
            raise FieldError("/new_password", code) from None
        user.set_password(password)
        user.save(update_fields=["password", "updated_at"])

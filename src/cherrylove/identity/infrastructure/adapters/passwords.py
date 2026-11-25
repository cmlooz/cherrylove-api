"""Passwords on Django's hashers and validators (Argon2, min length 10; ADR-004 §4)."""

from __future__ import annotations

import uuid

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from cherrylove.identity.application.commands.account import ProfileBefore
from cherrylove.identity.infrastructure.orm import User
from cherrylove.shared.domain.errors import FieldError
from cherrylove.shared.domain.ids import UserId

DJANGO_TO_FIELD_CODE = {"password_too_short": "too_short"}


class DjangoPasswords:
    def matches(self, user_id: UserId, password: str) -> bool:
        return User.objects.get(id=user_id.value).check_password(password)

    def set(self, user_id: UserId, password: str) -> None:
        user = User.objects.get(id=user_id.value)
        try:
            validate_password(password, user)
        except ValidationError as error:
            code = DJANGO_TO_FIELD_CODE.get(error.error_list[0].code or "", "invalid_format")
            raise FieldError("/new_password", code) from None
        user.set_password(password)
        user.save(update_fields=["password", "updated_at"])


class DjangoProfiles:
    def lock(self, user_id: UserId) -> ProfileBefore:
        user = User.objects.select_for_update().only("name", "language", "avatar_media_id").get(id=user_id.value)
        return ProfileBefore(user.name, user.language, user.avatar_media_id)

    def save(self, user_id: UserId, name: str, language: str, avatar_media_id: uuid.UUID | None) -> None:
        user = User.objects.get(id=user_id.value)
        user.name, user.language, user.avatar_media_id = name, language, avatar_media_id
        user.version += 1
        user.save(update_fields=["name", "language", "avatar_media_id", "version", "updated_at"])

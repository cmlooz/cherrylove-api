"""Identity ORM models (DATA-001 §3). The custom user model exists before any auth migration (ADR-004 §4)."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Length, Lower
from django.db.models.lookups import GreaterThanOrEqual


class UserManager(BaseUserManager["User"]):
    def create_user(self, email: str, password: str | None, **fields: Any) -> User:
        if not email:
            raise ValueError("email is required")
        user = self.model(email=email.strip().lower(), **fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None, **fields: Any) -> User:
        fields.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    # Stored lower-case; unique=True for Django auth, the lower(email) index guards any other writer.
    email = models.EmailField(max_length=254, unique=True)
    name = models.CharField(max_length=80)
    birth_date = models.DateField(null=True, blank=True)
    language = models.CharField(max_length=2, default="es")
    avatar_media_id = models.UUIDField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects: ClassVar[UserManager] = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["name"]

    class Meta:
        app_label = "identity"
        db_table = "identity_user"
        constraints: ClassVar = [
            models.UniqueConstraint(Lower("email"), name="identity_user_email_lower_uniq"),
            models.CheckConstraint(condition=models.Q(language__in=["es", "en"]), name="identity_user_language"),
            models.CheckConstraint(
                condition=GreaterThanOrEqual(Length("name"), 1), name="identity_user_name_not_empty"
            ),
        ]

    def __str__(self) -> str:
        return str(self.id)

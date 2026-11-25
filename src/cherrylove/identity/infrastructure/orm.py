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


class Couple(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active"
        ARCHIVED = "archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    relationship_start = models.DateField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="America/Bogota")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    archived_at = models.DateTimeField(null=True, blank=True)
    purge_after = models.DateField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "identity"
        db_table = "identity_couple"
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=models.Q(status__in=["active", "archived"]), name="identity_couple_status"
            ),
            models.CheckConstraint(
                condition=models.Q(status="archived", archived_at__isnull=False)
                | models.Q(status="active", archived_at__isnull=True),
                name="identity_couple_archived_at_matches_status",
            ),
        ]

    def __str__(self) -> str:
        return str(self.id)


class CoupleMembership(models.Model):
    """REQ-F-AUTH-05 lives here: two declarative uniques instead of a count query (DATA-001 §3)."""

    pk = models.CompositePrimaryKey("couple_id", "slot")
    couple = models.ForeignKey(Couple, on_delete=models.PROTECT, related_name="memberships")
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="membership")
    slot = models.PositiveSmallIntegerField()
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "identity"
        db_table = "identity_couple_membership"
        constraints: ClassVar = [
            models.CheckConstraint(condition=models.Q(slot__in=[1, 2]), name="identity_membership_slot"),
            # Target of the composite foreign keys of every couple-owned table (DATA-001 §1).
            models.UniqueConstraint(fields=["couple", "user"], name="identity_membership_couple_user_uniq"),
        ]

    def __str__(self) -> str:
        return f"{self.couple_id}:{self.slot}"


class Invite(models.Model):
    """DATA-001 §3. The token is issued by the send-email job; only its SHA-256 is ever stored (ADR-004 §4)."""

    class Status(models.TextChoices):
        PENDING = "pending"
        ACCEPTED = "accepted"
        REVOKED = "revoked"
        EXPIRED = "expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    couple = models.ForeignKey(Couple, on_delete=models.PROTECT, related_name="invites")
    slot = models.PositiveSmallIntegerField()
    email = models.EmailField(max_length=254)
    token_hash = models.BinaryField(null=True, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, related_name="+")
    sent_at = models.DateTimeField(null=True)
    accepted_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "identity"
        db_table = "identity_invite"
        constraints: ClassVar = [
            models.CheckConstraint(condition=models.Q(slot__in=[1, 2]), name="identity_invite_slot"),
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "accepted", "revoked", "expired"]),
                name="identity_invite_status",
            ),
            models.CheckConstraint(condition=models.Q(email=Lower("email")), name="identity_invite_email_lower"),
            # One live invite per seat (DATA-001 §3).
            models.UniqueConstraint(
                fields=["couple", "slot"],
                condition=models.Q(status="pending"),
                name="identity_invite_one_pending_per_seat",
            ),
        ]

    def __str__(self) -> str:
        return str(self.id)

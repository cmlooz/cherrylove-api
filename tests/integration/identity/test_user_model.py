"""Custom user model (IMPL-API-001 F2.1; ADR-004 §4, DATA-001 §3)."""

from __future__ import annotations

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connections, transaction
from django.db.migrations.loader import MigrationLoader

from cherrylove.identity.infrastructure.orm import User

pytestmark = pytest.mark.integration


@pytest.mark.req("REQ-F-AUTH-07")
def test_auth_user_model_is_created_by_the_first_identity_migration() -> None:
    assert settings.AUTH_USER_MODEL == "identity.User"
    assert get_user_model() is User
    first = MigrationLoader(None, ignore_no_migrations=True).graph.root_nodes("identity")[0]
    migration = MigrationLoader(None, ignore_no_migrations=True).graph.nodes[first]
    assert [op.name for op in migration.operations if type(op).__name__ == "CreateModel"] == ["User"]


@pytest.mark.req("REQ-F-AUTH-07")
@pytest.mark.django_db
def test_password_is_hashed_with_argon2_first() -> None:
    assert settings.PASSWORD_HASHERS[0] == "django.contrib.auth.hashers.Argon2PasswordHasher"
    user = User.objects.create_user("camila@example.com", "correct horse battery", name="Camila")
    assert user.password.startswith("argon2")
    assert user.check_password("correct horse battery")
    assert user.id.version == 7


@pytest.mark.req("REQ-F-AUTH-07")
@pytest.mark.django_db
def test_email_is_stored_lower_case_and_unique_ignoring_case() -> None:
    User.objects.create_user("  Camila@Example.COM ", "correct horse battery", name="Camila")
    assert User.objects.get().email == "camila@example.com"
    with transaction.atomic(), connections["default"].cursor() as cursor, pytest.raises(IntegrityError):
        cursor.execute(
            "INSERT INTO identity_user (id, email, password, name, language, is_active, is_staff, is_superuser,"
            " version, created_at, updated_at) VALUES (gen_random_uuid(), 'CAMILA@example.com', 'x', 'C', 'es',"
            " true, false, false, 1, now(), now())"
        )


@pytest.mark.req("REQ-F-AUTH-07")
@pytest.mark.django_db
@pytest.mark.parametrize(("field", "value"), [("language", "fr"), ("name", "")])
def test_database_checks_language_and_name(field: str, value: str) -> None:
    fields = {"name": "Camila", "language": "es", field: value}
    with transaction.atomic(), pytest.raises(IntegrityError):
        User.objects.create_user(f"{field}@example.com", "correct horse battery", **fields)

"""JWT issuer on PostgreSQL: the refresh token is tracked for rotation and blacklist (F2.9, ADR-004 §3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from cherrylove.identity.infrastructure.adapters.jwt_tokens import JwtTokenIssuer, MinimalAccessToken
from cherrylove.identity.infrastructure.orm import User
from cherrylove.shared.domain.ids import UserId

pytestmark = pytest.mark.integration


@pytest.mark.req("REQ-N-SEC-01")
@pytest.mark.django_db
def test_issued_session_is_tracked_and_expires_as_configured() -> None:
    user = User.objects.create_user(f"u.{uuid.uuid4().hex[:8]}@example.com", "correct horse battery", name="U")
    before = datetime.now(tz=UTC)
    session = JwtTokenIssuer().issue(UserId(user.id))

    assert MinimalAccessToken(session.access)["sub"] == str(user.id)
    assert timedelta(minutes=9) < session.access_expires_at - before <= timedelta(minutes=10, seconds=5)
    assert timedelta(days=29) < session.refresh_expires_at - before <= timedelta(days=30, seconds=5)
    assert OutstandingToken.objects.filter(user=user).count() == 1

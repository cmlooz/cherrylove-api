"""AuditLog port: field classification, diff without content, email HMAC (IMPL-API-001 F1.12, ADR-008 §2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from django.test import override_settings

from cherrylove.shared.application.audit_log import (
    AuditEvent,
    UnclassifiedFieldError,
    classify,
    diff,
    email_fingerprint,
    registered,
)
from cherrylove.shared.domain.actor import Membership
from cherrylove.shared.domain.ids import CoupleId, UserId
from cherrylove.shared.infrastructure.checks import audit_hmac_key_is_its_own
from tests.fakes.actor import InMemoryActorResolver
from tests.fakes.clock import FixedClock, SequentialIdGenerator


@dataclass
class ProbeCard:
    id: uuid.UUID
    body: str
    publish_at: datetime
    author_id: UserId


CARD = classify("probe_card", ProbeCard, loggable={"id", "publish_at", "author_id"}, content={"body"})
T1 = datetime(2026, 12, 1, tzinfo=UTC)
T2 = datetime(2026, 12, 24, tzinfo=UTC)


@pytest.mark.req("REQ-F-LOG-02")
def test_update_keeps_values_only_for_loggable_fields() -> None:
    changes = diff(CARD, {"body": "old secret", "publish_at": T1}, {"body": "new secret", "publish_at": T2})
    assert changes == {
        "body": {"changed": True},
        "publish_at": {"from": "2026-12-01T00:00:00+00:00", "to": "2026-12-24T00:00:00+00:00"},
    }
    assert "secret" not in str(changes)


@pytest.mark.req("REQ-F-LOG-02")
def test_unchanged_fields_are_left_out_and_creation_has_no_from() -> None:
    assert diff(CARD, {"body": "same", "publish_at": T1}, {"body": "same", "publish_at": T1}) == {}
    ids = SequentialIdGenerator(FixedClock())
    author = UserId(ids.new())
    created = diff(CARD, None, {"body": "hello", "publish_at": T1, "author_id": author})
    assert created == {
        "author_id": {"from": None, "to": str(author.value)},
        "body": {"changed": True},
        "publish_at": {"from": None, "to": "2026-12-01T00:00:00+00:00"},
    }


@pytest.mark.req("REQ-F-LOG-02")
def test_diffing_an_unclassified_field_fails() -> None:
    with pytest.raises(UnclassifiedFieldError, match=r"probe_card\.secret_note"):
        diff(CARD, None, {"secret_note": "x"})


@pytest.mark.req("REQ-F-LOG-02")
def test_registration_refuses_unclassified_unknown_or_overlapping_fields() -> None:
    with pytest.raises(UnclassifiedFieldError, match="unclassified \\['author_id'\\]"):
        classify("bad1", ProbeCard, loggable={"id", "publish_at"}, content={"body"})
    with pytest.raises(UnclassifiedFieldError, match="unknown \\['ghost'\\]"):
        classify("bad2", ProbeCard, loggable={"id", "publish_at", "author_id", "ghost"}, content={"body"})
    with pytest.raises(UnclassifiedFieldError, match="both loggable and content"):
        classify("bad3", ProbeCard, loggable={"id", "publish_at", "author_id", "body"}, content={"body"})
    assert not {"bad1", "bad2", "bad3"} & set(registered())


@pytest.mark.req("REQ-F-LOG-02")
def test_every_registered_entity_field_is_classified() -> None:
    """Architecture check over the registry: classification covers every field, exactly once."""
    for name, classification in registered().items():
        assert not classification.loggable & classification.content, name
        assert classification.loggable | classification.content, name


@pytest.mark.req("REQ-F-LOG-01")
def test_failed_login_email_is_an_hmac_never_the_email() -> None:
    first = email_fingerprint("  Camila@Example.com ", "key-a")
    assert first == email_fingerprint("camila@example.com", "key-a")
    assert first != email_fingerprint("camila@example.com", "key-b")
    assert "camila" not in first
    assert len(first) == 64


@pytest.mark.req("REQ-F-LOG-01")
def test_actor_type_follows_the_actor() -> None:
    ids = SequentialIdGenerator(FixedClock())
    user = UserId(ids.new())
    actor = InMemoryActorResolver(Membership(user, CoupleId(ids.new()), "es")).resolve(user)
    assert AuditEvent(action="card.created", actor=actor).resolved_actor_type == "partner"
    assert AuditEvent(action="auth.login_failed").resolved_actor_type == "anonymous"
    assert AuditEvent(action="card.published", actor_type="system").resolved_actor_type == "system"


@pytest.mark.req("REQ-F-LOG-01")
@pytest.mark.parametrize(
    ("overrides", "error_id"),
    [
        ({"AUDIT_HMAC_KEY": ""}, "cherrylove.E001"),
        ({"AUDIT_HMAC_KEY": "same-value", "SECRET_KEY": "same-value"}, "cherrylove.E002"),
        ({"AUDIT_HMAC_KEY": "same-value", "KEK": "same-value"}, "cherrylove.E002"),
    ],
)
def test_startup_check_rejects_empty_or_shared_keys(overrides: dict[str, str], error_id: str) -> None:
    with override_settings(**overrides):
        assert [message.id for message in audit_hmac_key_is_its_own()] == [error_id]


@pytest.mark.req("REQ-F-LOG-01")
def test_startup_check_passes_with_an_own_key() -> None:
    assert audit_hmac_key_is_its_own() == []

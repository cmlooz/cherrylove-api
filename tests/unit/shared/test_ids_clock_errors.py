"""UUIDv7 value object, clock fake and base domain errors (IMPL-API-001 F1.1; ADR-006 §8, ADR-010 §3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cherrylove.shared.domain.errors import DomainError, EntityDeleted, FieldError, NotAuthor, NotFound
from cherrylove.shared.domain.ids import CoupleId, UserId, Uuid7, timestamp_of
from cherrylove.shared.infrastructure.clock import SystemClock, Uuid7Generator
from tests.fakes.clock import FixedClock, SequentialIdGenerator, uuid7_at

CLOCK = FixedClock()
SKEW = timedelta(hours=24)
offsets = st.timedeltas(min_value=-timedelta(days=3650), max_value=SKEW)


@pytest.mark.req("REQ-F-SYNC-03")
@given(offset=offsets, tail=st.integers(min_value=0, max_value=(1 << 74) - 1))
def test_accepts_version_7_up_to_24_hours_ahead(offset: timedelta, tail: int) -> None:
    raw = uuid7_at(CLOCK.now() + offset, tail)
    parsed = Uuid7.parse(str(raw), CLOCK)
    assert parsed.value == raw
    assert str(parsed) == str(raw)


@pytest.mark.req("REQ-F-SYNC-03")
@given(offset=st.timedeltas(min_value=SKEW + timedelta(milliseconds=1), max_value=timedelta(days=3650)))
def test_rejects_timestamps_more_than_24_hours_ahead(offset: timedelta) -> None:
    with pytest.raises(FieldError) as error:
        Uuid7.parse(uuid7_at(CLOCK.now() + offset), CLOCK)
    assert error.value.field_code == "timestamp_too_far_ahead"
    assert error.value.params == {"max_hours": 24}


@pytest.mark.req("REQ-F-SYNC-03")
@given(version=st.sampled_from([1, 3, 4, 5, 6, 8]), value=st.integers(min_value=0, max_value=(1 << 128) - 1))
def test_rejects_every_other_version(version: int, value: int) -> None:
    raw = uuid.UUID(int=value, version=version)
    with pytest.raises(FieldError) as error:
        Uuid7.parse(raw, CLOCK, pointer="/body/id")
    assert error.value.field_code == "invalid_uuid_version"
    assert error.value.pointer == "/body/id"


@pytest.mark.req("REQ-F-SYNC-03")
@pytest.mark.parametrize("raw", ["", "not-a-uuid", "0193a5b2-7c3e-7d4a-9f00"])
def test_rejects_malformed_strings(raw: str) -> None:
    with pytest.raises(FieldError) as error:
        Uuid7.parse(raw, CLOCK)
    assert error.value.field_code == "invalid_format"


@pytest.mark.req("REQ-F-SYNC-03")
def test_timestamp_is_the_millisecond_prefix() -> None:
    instant = datetime(2026, 11, 18, 14, 0, 0, 123000, tzinfo=UTC)
    assert timestamp_of(uuid7_at(instant)) == instant


@pytest.mark.req("REQ-F-SYNC-03")
def test_typed_ids_are_not_interchangeable() -> None:
    raw = uuid7_at(CLOCK.now())
    couple, user = CoupleId.parse(raw, CLOCK), UserId.parse(raw, CLOCK)
    assert type(couple) is CoupleId
    assert type(user) is UserId


@pytest.mark.req("REQ-F-SYNC-03")
def test_system_generator_and_fakes_produce_valid_uuid7() -> None:
    system_clock = SystemClock()
    assert system_clock.now().tzinfo is UTC
    assert Uuid7.parse(Uuid7Generator().new(), system_clock).value.version == 7
    generator = SequentialIdGenerator(CLOCK)
    first, second = generator.new(), generator.new()
    assert first != second
    assert timestamp_of(first) == CLOCK.now()


@pytest.mark.req("REQ-F-SYNC-03")
def test_fixed_clock_only_moves_when_told() -> None:
    clock = FixedClock()
    start = clock.now()
    assert clock.now() == start
    clock.advance(timedelta(minutes=5))
    assert clock.now() == start + timedelta(minutes=5)


@pytest.mark.req("REQ-N-QA-02")
@pytest.mark.parametrize(
    ("error", "code", "status"),
    [
        (DomainError(), "internal_error", 500),
        (FieldError("/body", "too_long", max=10), "validation_failed", 400),
        (NotFound(), "not_found", 404),
        (NotAuthor(), "not_author", 403),
        (EntityDeleted(), "entity_deleted", 410),
    ],
)
def test_each_error_class_has_code_status_and_params(error: DomainError, code: str, status: int) -> None:
    assert (error.code, error.status) == (code, status)
    assert isinstance(dict(error.params), dict)


@pytest.mark.req("REQ-N-QA-02")
def test_params_merge_defaults_and_are_read_only() -> None:
    class QuotaExceeded(DomainError):
        code = "quota_exceeded"
        status = 409
        default_params = {"unit": "bytes"}  # noqa: RUF012 - test subclass

    error = QuotaExceeded("over the limit", limit=5)
    assert error.params == {"unit": "bytes", "limit": 5}
    assert str(error) == "over the limit"
    with pytest.raises(TypeError):
        error.params["limit"] = 6  # type: ignore[index]

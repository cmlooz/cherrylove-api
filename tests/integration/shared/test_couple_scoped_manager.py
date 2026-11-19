"""Fail-closed couple-scoped manager on PostgreSQL (IMPL-API-001 F1.6, ADR-005 §3, REQ-N-SEC-01)."""

from __future__ import annotations

import uuid

import pytest

from cherrylove.shared.domain.ids import CoupleId
from cherrylove.shared.infrastructure.scoping import UnscopedQueryError
from tests.apps.scoping.models import ScopedProbe
from tests.fakes.clock import FixedClock, SequentialIdGenerator

pytestmark = pytest.mark.integration

IDS = SequentialIdGenerator(FixedClock())
COUPLE_A = CoupleId(IDS.new())
COUPLE_B = CoupleId(IDS.new())


@pytest.fixture
def rows() -> None:
    ScopedProbe(couple_id=COUPLE_A.value, note="a1").save()
    ScopedProbe(couple_id=COUPLE_A.value, note="a2").save()
    ScopedProbe(couple_id=COUPLE_B.value, note="b1").save()


@pytest.mark.req("REQ-N-SEC-01")
@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    [
        ScopedProbe.objects.all,
        lambda: ScopedProbe.objects.filter(note="a1"),
        ScopedProbe.objects.count,
        lambda: ScopedProbe.objects.get(note="a1"),
        lambda: ScopedProbe.objects.create(couple_id=COUPLE_A.value, note="x"),
    ],
    ids=["all", "filter", "count", "get", "create"],
)
def test_default_queryset_raises(rows: None, query: object) -> None:
    with pytest.raises(UnscopedQueryError):
        query()  # type: ignore[operator]


@pytest.mark.req("REQ-N-SEC-01")
@pytest.mark.django_db
def test_for_couple_returns_only_that_couple(rows: None) -> None:
    notes = sorted(ScopedProbe.objects.for_couple(COUPLE_A).values_list("note", flat=True))
    assert notes == ["a1", "a2"]
    assert list(ScopedProbe.objects.for_couple(COUPLE_B).values_list("note", flat=True)) == ["b1"]


@pytest.mark.req("REQ-N-SEC-01")
@pytest.mark.django_db
def test_for_couple_demands_a_couple_id_not_a_raw_uuid(rows: None) -> None:
    with pytest.raises(TypeError):
        ScopedProbe.objects.for_couple(uuid.uuid4())  # type: ignore[arg-type]


@pytest.mark.req("REQ-N-SEC-01")
@pytest.mark.django_db
def test_instance_writes_and_refresh_still_work(rows: None) -> None:
    probe = ScopedProbe.objects.for_couple(COUPLE_B).get()
    probe.note = "b1-edited"
    probe.save()
    probe.refresh_from_db()
    assert probe.note == "b1-edited"

"""Phase F1 integration test (IMPL-API-001 §5): audit + job + recorded change in one unit of work.

On a domain error nothing persists and the response is Problem Details carrying the request's request_id;
on success all three exist.
"""

from __future__ import annotations

import uuid

import pytest
from django.db import connections
from django.test import Client
from django_tasks_db.models import DBTaskResult

from tests.apps.scoping.models import ProbeChange

pytestmark = pytest.mark.integration


def _audited(entity_id: uuid.UUID) -> int:
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT count(*) FROM audit_event WHERE entity_id = %s", [entity_id])
        row = cursor.fetchone()
    assert row is not None
    return int(row[0])


def _enqueued(entity_id: uuid.UUID) -> int:
    key = f"probe:{entity_id}"
    return sum(1 for row in DBTaskResult.objects.all() if row.args_kwargs["args"][2] == key)


def _post(client: Client, *, fail: bool) -> tuple[uuid.UUID, object]:
    entity_id = uuid.uuid7()
    response = client.post(
        "/probe",
        {"couple_id": str(uuid.uuid7()), "entity_id": str(entity_id), "fail": fail},
        content_type="application/json",
        headers={"X-Request-ID": "phase1-trace"},
    )
    return entity_id, response


@pytest.mark.req("REQ-N-QA-02")
@pytest.mark.urls("tests.apps.scoping.kernel_probe")
@pytest.mark.django_db(transaction=True)
def test_failure_persists_nothing_and_answers_problem_details(client: Client) -> None:
    entity_id, response = _post(client, fail=True)
    assert response.status_code == 403  # type: ignore[attr-defined]
    assert response["Content-Type"] == "application/problem+json"  # type: ignore[index]
    body = response.json()  # type: ignore[attr-defined]
    assert (body["code"], body["request_id"]) == ("not_author", "phase1-trace")
    assert not ProbeChange.objects.filter(entity_id=entity_id).exists()
    assert _audited(entity_id) == 0
    assert _enqueued(entity_id) == 0


@pytest.mark.req("REQ-N-QA-02")
@pytest.mark.urls("tests.apps.scoping.kernel_probe")
@pytest.mark.django_db(transaction=True)
def test_success_persists_change_audit_and_job_together(client: Client) -> None:
    entity_id, response = _post(client, fail=False)
    assert response.status_code == 204  # type: ignore[attr-defined]
    assert response["X-Request-ID"] == "phase1-trace"  # type: ignore[index]
    assert ProbeChange.objects.filter(entity_id=entity_id, entity_type="note").count() == 1
    assert _audited(entity_id) == 1
    assert _enqueued(entity_id) == 1

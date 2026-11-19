"""Test-only probe use case over the whole shared kernel (IMPL-API-001 F1 phase integration test).

One unit of work records a change, writes an audit event and enqueues a job; on a domain error nothing
persists and the HTTP layer answers with Problem Details.
"""

from __future__ import annotations

import uuid

from django.urls import path
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from cherrylove.audit.infrastructure.postgres_audit_log import PostgresAuditLog
from cherrylove.shared.application.audit_log import AuditEvent, AuditLog
from cherrylove.shared.application.change_recorder import ChangeRecorder, EntityType
from cherrylove.shared.application.job_queue import JobQueue, Payload
from cherrylove.shared.application.unit_of_work import UnitOfWork
from cherrylove.shared.domain.errors import NotAuthor
from cherrylove.shared.domain.ids import CoupleId, UserId
from cherrylove.shared.infrastructure.clock import SystemClock, Uuid7Generator
from cherrylove.shared.infrastructure.django_job_queue import DjangoJobQueue, register_job
from cherrylove.shared.infrastructure.django_unit_of_work import DjangoUnitOfWork
from tests.apps.scoping.models import ProbeChange


class ProbeChangeRecorder:
    def record(
        self, couple_id: CoupleId, entity_type: EntityType, entity_id: uuid.UUID, author_id: UserId | None
    ) -> None:
        ProbeChange(
            couple_id=couple_id.value,
            entity_type=entity_type,
            entity_id=entity_id,
            author_id=author_id.value if author_id else None,
        ).save()


@register_job("test.probe.kernel")
def kernel_job(payload: Payload) -> None:
    return None


class ProbeUseCase:
    def __init__(self, uow: UnitOfWork, audit: AuditLog, jobs: JobQueue, changes: ChangeRecorder) -> None:
        self.uow, self.audit, self.jobs, self.changes = uow, audit, jobs, changes

    def execute(self, couple_id: CoupleId, entity_id: uuid.UUID, *, fail: bool) -> None:
        with self.uow.atomic():
            self.changes.record(couple_id, "note", entity_id, None)
            self.audit.record(
                AuditEvent(action="probe.created", actor_type="system", entity_type="note", entity_id=entity_id)
            )
            self.jobs.enqueue("test.probe.kernel", {"id": str(entity_id)}, idempotency_key=f"probe:{entity_id}")
            if fail:
                raise NotAuthor("probe failure")


class ProbeView(APIView):
    authentication_classes = ()
    permission_classes = ()

    def post(self, request: Request) -> Response:
        use_case = ProbeUseCase(
            DjangoUnitOfWork(),
            PostgresAuditLog(SystemClock(), Uuid7Generator()),
            DjangoJobQueue(),
            ProbeChangeRecorder(),
        )
        data: dict[str, object] = dict(request.data)
        use_case.execute(
            CoupleId(uuid.UUID(str(data["couple_id"]))),
            uuid.UUID(str(data["entity_id"])),
            fail=bool(data.get("fail")),
        )
        return Response(status=204)


urlpatterns = [path("probe", ProbeView.as_view())]
handler404 = "cherrylove.shared.interfaces.http.problem_details.not_found_view"

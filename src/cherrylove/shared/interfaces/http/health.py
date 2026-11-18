"""Liveness + database probe for containers and load balancers. Operational, not part of the contract."""

from __future__ import annotations

from django.db import connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request: HttpRequest) -> JsonResponse:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})

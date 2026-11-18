"""Root URLs. `/healthz` sits outside `/api/v1` and outside the contract (IMPL-API-001 F0)."""

from __future__ import annotations

from django.urls import path

from cherrylove.shared.interfaces.http.health import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
]

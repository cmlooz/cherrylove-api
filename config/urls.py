"""Root URLs. `/healthz` sits outside `/api/v1` and outside the contract (IMPL-API-001 F0)."""

from __future__ import annotations

from django.urls import include, path

from cherrylove.shared.interfaces.http.health import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("api/v1/", include("cherrylove.identity.interfaces.http.urls")),
]

# Unknown URLs and unhandled errors answer as RFC 9457 problems too (ADR-010).
handler404 = "cherrylove.shared.interfaces.http.problem_details.not_found_view"
handler500 = "cherrylove.shared.interfaces.http.problem_details.server_error_view"

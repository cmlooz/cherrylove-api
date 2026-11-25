"""Identity routes under /api/v1 (API-001)."""

from __future__ import annotations

from django.urls import path

from cherrylove.identity.interfaces.http.views import AcceptInviteView, InviteView

urlpatterns = [
    path("invites/<str:token>", InviteView.as_view(), name="identity_get_invite"),
    path("invites/<str:token>/accept", AcceptInviteView.as_view(), name="identity_accept_invite"),
]

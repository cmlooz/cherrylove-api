"""Identity routes under /api/v1 (API-001)."""

from __future__ import annotations

from django.urls import path

from cherrylove.identity.interfaces.http.session_views import LoginView, LogoutView, RefreshView
from cherrylove.identity.interfaces.http.views import AcceptInviteView, InviteView

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="identity_create_session"),
    path("auth/refresh", RefreshView.as_view(), name="identity_refresh_session"),
    path("auth/logout", LogoutView.as_view(), name="identity_delete_session"),
    path("invites/<str:token>", InviteView.as_view(), name="identity_get_invite"),
    path("invites/<str:token>/accept", AcceptInviteView.as_view(), name="identity_accept_invite"),
]

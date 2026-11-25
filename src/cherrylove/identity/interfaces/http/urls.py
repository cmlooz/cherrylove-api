"""Identity routes under /api/v1 (API-001)."""

from __future__ import annotations

from django.urls import path

from cherrylove.identity.interfaces.http.account_views import ChangePasswordView, CoupleView, MeView
from cherrylove.identity.interfaces.http.recovery_views import ConfirmRecoveryView, RequestRecoveryView
from cherrylove.identity.interfaces.http.session_views import LoginView, LogoutView, RefreshView
from cherrylove.identity.interfaces.http.views import AcceptInviteView, InviteView

urlpatterns = [
    path("me", MeView.as_view(), name="identity_me"),
    path("me/password", ChangePasswordView.as_view(), name="identity_change_password"),
    path("couple", CoupleView.as_view(), name="home_get_couple"),
    path("auth/login", LoginView.as_view(), name="identity_create_session"),
    path("auth/refresh", RefreshView.as_view(), name="identity_refresh_session"),
    path("auth/logout", LogoutView.as_view(), name="identity_delete_session"),
    path("auth/password-recovery", RequestRecoveryView.as_view(), name="identity_request_password_recovery"),
    path(
        "auth/password-recovery/confirm",
        ConfirmRecoveryView.as_view(),
        name="identity_confirm_password_recovery",
    ),
    path("invites/<str:token>", InviteView.as_view(), name="identity_get_invite"),
    path("invites/<str:token>/accept", AcceptInviteView.as_view(), name="identity_accept_invite"),
]

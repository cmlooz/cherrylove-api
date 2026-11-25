"""Identity HTTP adapters (ADR-001 §2): parse, call one use case, render. No try/except (ADR-010)."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from cherrylove.identity import wiring
from cherrylove.identity.application.commands.onboarding import Onboarding
from cherrylove.identity.interfaces.http.serializers import (
    InvitePreviewSerializer,
    OnboardingInputSerializer,
    TokenPairSerializer,
)
from cherrylove.identity.interfaces.http.sessions import session_response
from cherrylove.shared.interfaces.http.contract import error_headers, error_responses
from cherrylove.shared.interfaces.http.throttling import FailClosedScopedThrottle, FailOpenScopedThrottle


class InviteView(APIView):
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = (FailOpenScopedThrottle,)  # viewing an invite is not an auth attempt
    throttle_scope = "invite"

    @extend_schema(
        operation_id="identity_get_invite",
        tags=["identity"],
        auth=[],
        parameters=error_headers("identity_get_invite"),
        responses={200: InvitePreviewSerializer, **error_responses("identity_get_invite")},
    )
    def get(self, request: Request, token: str) -> Response:
        preview = wiring.get_invite().execute(token)
        return Response(InvitePreviewSerializer(preview).data)


class AcceptInviteView(APIView):
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = (FailClosedScopedThrottle,)  # accepting sets a password: auth scope (ADR-011 §2)
    throttle_scope = "invite"

    @extend_schema(
        operation_id="identity_accept_invite",
        tags=["identity"],
        auth=[],
        request=OnboardingInputSerializer,
        parameters=error_headers("identity_accept_invite"),
        responses={201: TokenPairSerializer, **error_responses("identity_accept_invite")},
    )
    def post(self, request: Request, token: str) -> Response:
        data = OnboardingInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        session = wiring.accept_invite().execute(token, Onboarding(**data.validated_data))
        return session_response(request, session, status=201)

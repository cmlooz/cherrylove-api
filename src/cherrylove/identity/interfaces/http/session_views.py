"""Login, refresh and logout (ADR-004 §2): one use case per view, no try/except (ADR-010)."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from cherrylove.identity import wiring
from cherrylove.identity.application.commands.sessions import RequestInfo
from cherrylove.identity.interfaces.http.authentication import PartnerJWTAuthentication
from cherrylove.identity.interfaces.http.serializers import (
    LoginInputSerializer,
    RefreshInputSerializer,
    TokenPairSerializer,
)
from cherrylove.identity.interfaces.http.sessions import (
    CLIENT_HEADER,
    clear_refresh_cookie,
    is_web,
    refresh_from,
    session_response,
)
from cherrylove.shared.interfaces.http.contract import error_headers, error_responses
from cherrylove.shared.interfaces.http.throttling import IpAndEmailThrottle

REQUEST_ID = OpenApiParameter(
    "X-Request-ID", type={"type": "string", "maxLength": 64}, location=OpenApiParameter.HEADER, required=False
)
CLIENT = OpenApiParameter(
    CLIENT_HEADER,
    type={"type": "string", "enum": ["web", "mobile"]},
    location=OpenApiParameter.HEADER,
    required=False,
)


# Cookie or body (API-001); extend_schema accepts raw requirements although its stubs say list[str].
REFRESH_SECURITY: Any = [{"refreshCookie": []}, {}]


def _info(request: Request, client: str) -> RequestInfo:
    return RequestInfo(ip=request.META.get("REMOTE_ADDR"), client=client)


class LoginView(APIView):
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = (IpAndEmailThrottle,)
    throttle_scope = "login"

    @extend_schema(
        operation_id="identity_create_session",
        tags=["identity"],
        auth=[],
        request=LoginInputSerializer,
        parameters=[REQUEST_ID, *error_headers("identity_create_session")],
        responses={200: TokenPairSerializer, **error_responses("identity_create_session")},
    )
    def post(self, request: Request) -> Response:
        data = LoginInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        client = str(data.validated_data["client"])
        session = wiring.login().execute(
            data.validated_data["email"], data.validated_data["password"], _info(request, client)
        )
        return session_response(request, session, status=200, web=client == "web")


class RefreshView(APIView):
    authentication_classes = ()
    permission_classes = ()

    @extend_schema(
        operation_id="identity_refresh_session",
        tags=["identity"],
        auth=REFRESH_SECURITY,
        request=RefreshInputSerializer,
        parameters=[REQUEST_ID, CLIENT],
        responses={200: TokenPairSerializer, **error_responses("identity_refresh_session")},
    )
    def post(self, request: Request) -> Response:
        data = RefreshInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        refresh = refresh_from(request, data.validated_data.get("refresh"))
        client = "web" if is_web(request) else "mobile"
        session = wiring.refresh_session().execute(refresh, _info(request, client))
        return session_response(request, session, status=200)


class LogoutView(APIView):
    authentication_classes = (PartnerJWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        operation_id="identity_delete_session",
        tags=["identity"],
        request=RefreshInputSerializer,
        parameters=[REQUEST_ID, CLIENT],
        responses={204: None, **error_responses("identity_delete_session")},
    )
    def post(self, request: Request) -> Response:
        data = RefreshInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        refresh = refresh_from(request, data.validated_data.get("refresh"))
        client = "web" if is_web(request) else "mobile"
        wiring.logout().execute(refresh, _info(request, client))
        response = Response(status=204)
        if is_web(request):
            clear_refresh_cookie(response)
        return response

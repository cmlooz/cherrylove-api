"""Password recovery endpoints (REQ-F-AUTH-08): identical answers whether the email exists or not."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from cherrylove.identity import wiring
from cherrylove.identity.interfaces.http.serializers import RecoveryConfirmSerializer, RecoveryRequestSerializer
from cherrylove.shared.interfaces.http.contract import error_headers, error_responses
from cherrylove.shared.interfaces.http.throttling import RecoveryEmailThrottle, RecoveryUidThrottle


class RequestRecoveryView(APIView):
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = (RecoveryEmailThrottle,)
    throttle_scope = "recovery"

    @extend_schema(
        operation_id="identity_request_password_recovery",
        tags=["identity"],
        auth=[],
        request=RecoveryRequestSerializer,
        parameters=error_headers("identity_request_password_recovery"),
        responses={202: None, **error_responses("identity_request_password_recovery")},
    )
    def post(self, request: Request) -> Response:
        data = RecoveryRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        wiring.request_password_recovery().execute(data.validated_data["email"])
        return Response(status=202)


class ConfirmRecoveryView(APIView):
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = (RecoveryUidThrottle,)
    throttle_scope = "recovery"

    @extend_schema(
        operation_id="identity_confirm_password_recovery",
        tags=["identity"],
        auth=[],
        request=RecoveryConfirmSerializer,
        parameters=error_headers("identity_confirm_password_recovery"),
        responses={204: None, **error_responses("identity_confirm_password_recovery")},
    )
    def post(self, request: Request) -> Response:
        data = RecoveryConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        wiring.confirm_password_recovery().execute(values["uid"], values["token"], values["new_password"])
        return Response(status=204)

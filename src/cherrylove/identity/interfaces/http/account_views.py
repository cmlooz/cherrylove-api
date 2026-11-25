"""My account and the couple header (REQ-F-ACC-01…04, REQ-F-HOME-01): one use case per method (ADR-010)."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from cherrylove.identity import wiring
from cherrylove.identity.application.commands.account import UNSET, ProfileChanges
from cherrylove.identity.interfaces.http.authentication import PartnerJWTAuthentication
from cherrylove.identity.interfaces.http.serializers import (
    ChangePasswordInputSerializer,
    CoupleSerializer,
    MeInputSerializer,
    MeSerializer,
)
from cherrylove.shared.interfaces.http.actor import IsCouplePartner, Partner, actor_of
from cherrylove.shared.interfaces.http.contract import error_headers, error_responses
from cherrylove.shared.interfaces.http.openapi import RequiredBodySchema


class PartnerView(APIView):
    authentication_classes = (PartnerJWTAuthentication,)
    permission_classes = (IsCouplePartner,)


class MeView(PartnerView):
    schema = RequiredBodySchema()

    @extend_schema(
        operation_id="identity_get_me",
        tags=["identity"],
        parameters=error_headers("identity_get_me"),
        responses={200: MeSerializer, **error_responses("identity_get_me")},
    )
    def get(self, request: Request) -> Response:
        return Response(MeSerializer(wiring.get_me().execute(actor_of(request))).data)

    @extend_schema(
        operation_id="identity_update_me",
        tags=["identity"],
        request=MeInputSerializer,
        parameters=error_headers("identity_update_me"),
        responses={200: MeSerializer, **error_responses("identity_update_me")},
    )
    def patch(self, request: Request) -> Response:
        data = MeInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data
        actor = actor_of(request)
        changes = ProfileChanges(
            name=fields.get("name"),
            language=fields.get("language"),
            avatar_media_id=fields.get("avatar_media_id", UNSET),
        )
        wiring.update_me().execute(actor, changes)
        return Response(MeSerializer(wiring.get_me().execute(actor)).data)


class ChangePasswordView(PartnerView):
    @extend_schema(
        operation_id="identity_change_password",
        tags=["identity"],
        request=ChangePasswordInputSerializer,
        parameters=error_headers("identity_change_password"),
        responses={204: None, **error_responses("identity_change_password")},
    )
    def post(self, request: Request) -> Response:
        data = ChangePasswordInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        partner = request.user
        session_id = partner.session_id if isinstance(partner, Partner) else None
        wiring.change_password().execute(
            actor_of(request), session_id, data.validated_data["current_password"], data.validated_data["new_password"]
        )
        return Response(status=204)


class CoupleView(PartnerView):
    @extend_schema(
        operation_id="home_get_couple",
        tags=["home"],
        parameters=error_headers("home_get_couple"),
        responses={200: CoupleSerializer, **error_responses("home_get_couple")},
    )
    def get(self, request: Request) -> Response:
        return Response(CoupleSerializer(wiring.get_couple_header().execute(actor_of(request))).data)

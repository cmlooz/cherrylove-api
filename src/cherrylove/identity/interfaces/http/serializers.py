"""Identity wire shapes; their generated schemas must equal the contract (ADR-003 §2, DEC-048)."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

LANGUAGES = [("es", "es"), ("en", "en")]


class InvitePreviewSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()
    relationship_start_known = serializers.BooleanField()


class OnboardingInputSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(min_length=1, max_length=80)
    birth_date = serializers.DateField()
    password = serializers.CharField(min_length=10, trim_whitespace=False)
    relationship_start = serializers.DateField(required=False)
    language = serializers.ChoiceField(choices=LANGUAGES, required=False)


class TokenPairSerializer(serializers.Serializer[Any]):
    access = serializers.CharField()
    access_expires_at = serializers.DateTimeField()
    refresh = serializers.CharField(required=False)


@extend_schema_field({"type": "string", "format": "email"})
class ContractEmailField(serializers.Field):  # type: ignore[type-arg]
    """Any string, blank included: a malformed or unknown email fails exactly like a wrong password, with the
    contract's schema and no extra constraints (ADR-004 §4)."""

    default_error_messages = {"invalid": "Not a string."}  # noqa: RUF012 - DRF convention

    def to_internal_value(self, data: object) -> str:
        if not isinstance(data, str):
            self.fail("invalid")
        return data

    def to_representation(self, value: object) -> str:
        return str(value)


class LoginInputSerializer(serializers.Serializer[Any]):
    email = ContractEmailField()
    # Blank is not a 400: the contract has no minLength, so it fails as invalid_credentials.
    password = serializers.CharField(trim_whitespace=False, allow_blank=True)
    client = serializers.ChoiceField(choices=[("web", "web"), ("mobile", "mobile")])


class RefreshInputSerializer(serializers.Serializer[Any]):
    refresh = serializers.CharField(required=False, allow_blank=True)


class RecoveryRequestSerializer(serializers.Serializer[Any]):
    email = ContractEmailField()


class RecoveryConfirmSerializer(serializers.Serializer[Any]):
    # Blank uid/token fail as invalid_token, never as a different error (no hint which part was wrong).
    uid = serializers.CharField(allow_blank=True)
    token = serializers.CharField(allow_blank=True)
    new_password = serializers.CharField(min_length=10, trim_whitespace=False)


# drf-spectacular appends `{type: null}` to a `oneOf` of an allow_null field: the contract's `Uuid | null`.
@extend_schema_field({"oneOf": [{"type": "string", "format": "uuid"}]})
class NullableUuidField(serializers.UUIDField):
    """`Uuid | null` exactly as the contract writes it."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(allow_null=True, **kwargs)


class PersonSummarySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    avatar_media_id = NullableUuidField(required=False)


class MeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    name = serializers.CharField()
    birth_date = serializers.DateField(required=False)
    language = serializers.ChoiceField(choices=LANGUAGES)
    avatar_media_id = NullableUuidField(required=False)
    partner = PersonSummarySerializer(required=False, allow_null=True)

    def to_representation(self, instance: Any) -> dict[str, Any]:
        data = dict(super().to_representation(instance))
        if data.get("birth_date") is None:
            data.pop("birth_date", None)  # optional and not nullable in the contract
        return data


class MeInputSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(min_length=1, max_length=80, required=False)
    language = serializers.ChoiceField(choices=LANGUAGES, required=False)
    avatar_media_id = NullableUuidField(required=False)


class ChangePasswordInputSerializer(serializers.Serializer[Any]):
    current_password = serializers.CharField(trim_whitespace=False, allow_blank=True)
    new_password = serializers.CharField(min_length=10, trim_whitespace=False)


@extend_schema_field({"oneOf": [{"type": "string", "format": "date"}]})
class NullableDateField(serializers.DateField):
    """`CivilDate | null` as a `oneOf`, like the contract."""


class CoupleSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    partners = serializers.ListField(child=PersonSummarySerializer(), max_length=2)
    relationship_start = NullableDateField(required=False, allow_null=True)
    days_together = serializers.IntegerField(required=False, allow_null=True)
    timezone = serializers.CharField()
    version = serializers.IntegerField()

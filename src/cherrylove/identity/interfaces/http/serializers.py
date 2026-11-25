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
class LoginEmailField(serializers.Field):  # type: ignore[type-arg]
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
    email = LoginEmailField()
    # Blank is not a 400: the contract has no minLength, so it fails as invalid_credentials.
    password = serializers.CharField(trim_whitespace=False, allow_blank=True)
    client = serializers.ChoiceField(choices=[("web", "web"), ("mobile", "mobile")])


class RefreshInputSerializer(serializers.Serializer[Any]):
    refresh = serializers.CharField(required=False, allow_blank=True)

"""Identity wire shapes; their generated schemas must equal the contract (ADR-003 §2, DEC-048)."""

from __future__ import annotations

from typing import Any

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

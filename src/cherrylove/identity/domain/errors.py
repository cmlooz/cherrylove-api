"""Identity domain errors (ADR-010 §2; codes from the contract ErrorCode)."""

from __future__ import annotations

from cherrylove.shared.domain.errors import DomainError


class EmailAlreadyInCouple(DomainError):
    """REQ-F-AUTH-10: an email that already belongs to a couple cannot be invited again."""

    code = "email_already_in_couple"
    status = 409


class InviteExpired(DomainError):
    code = "invite_expired"
    status = 409


class InviteRevoked(DomainError):
    code = "invite_revoked"
    status = 409


class CoupleFull(DomainError):
    code = "couple_full"
    status = 409


class CoupleArchived(DomainError):
    code = "couple_archived"
    status = 409


class InvalidCredentials(DomainError):
    """Wrong email or password: the same answer for an unknown email (ADR-004 §4)."""

    code = "invalid_credentials"
    status = 401


class ClientHeaderRequired(DomainError):
    """A cookie-based call without `X-CherryLove-Client: web` (CSRF defense, ADR-004 §2)."""

    code = "client_header_required"
    status = 403

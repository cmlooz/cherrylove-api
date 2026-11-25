"""Identity domain errors (ADR-010 §2; codes from the contract ErrorCode)."""

from __future__ import annotations

from cherrylove.shared.domain.errors import DomainError


class EmailAlreadyInCouple(DomainError):
    """REQ-F-AUTH-10: an email that already belongs to a couple cannot be invited again."""

    code = "email_already_in_couple"
    status = 409

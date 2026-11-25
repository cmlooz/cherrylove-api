"""`manage.py create_couple` until the backoffice UI exists (F9): an inbound adapter, like a view."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from cherrylove.identity import wiring
from cherrylove.shared.domain.errors import DomainError


class CreateCoupleCommand(BaseCommand):
    help = "Create a couple and invite both partners by email (REQ-F-AUTH-01, DEC-028)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("first_email")
        parser.add_argument("second_email")

    def handle(self, *args: Any, **options: Any) -> None:
        # CLI counterpart of the problem-details handler: a domain error becomes a clean CommandError.
        try:
            couple_id = wiring.create_couple().execute(options["first_email"], options["second_email"])
        except DomainError as error:
            raise CommandError(f"{error.code}: {error.detail or error}") from error
        self.stdout.write(str(couple_id))

"""Test database built the production way: created and migrated by the maintenance role,
then used by the app role (ADR-008 §4, ADR-014 §1)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.db import connections
from pytest_django import DjangoDbBlocker


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment: None, django_db_blocker: DjangoDbBlocker) -> Iterator[None]:
    maintenance = connections["maintenance"]
    default = connections["default"]
    original_name = maintenance.settings_dict["NAME"]
    with django_db_blocker.unblock():
        test_name = maintenance.creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
        default.close()
        default.settings_dict["NAME"] = test_name
    yield
    with django_db_blocker.unblock():
        default.close()
        maintenance.creation.destroy_test_db(original_name, verbosity=0)

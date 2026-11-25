"""Every table and sequence the maintenance role creates is usable by the app role with DML only.

Runs as `cherrylove_maintenance` (the only alias allowed to migrate), so `ALTER DEFAULT PRIVILEGES`
applies to objects that role creates from now on, in this database (ADR-008 §4, DATA-001 §3).
"""

from __future__ import annotations

from django.db import migrations

APP_ROLE = "cherrylove_app"

GRANT = f"""
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE};
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE};
GRANT SELECT ON django_migrations TO {APP_ROLE};
"""

REVOKE = f"""
REVOKE SELECT ON django_migrations FROM {APP_ROLE};
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE USAGE, SELECT ON SEQUENCES FROM {APP_ROLE};
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE};
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    # Third-party tables must be created after the default privileges too (tests/architecture).
    run_before = [
        ("django_tasks_database", "0001_initial"),
        ("contenttypes", "0001_initial"),
        ("auth", "0001_initial"),
        ("token_blacklist", "0001_initial"),
    ]
    operations = [migrations.RunSQL(GRANT, REVOKE)]

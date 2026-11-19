"""Probe table for the fail-closed manager tests, created after the default privileges (shared.0001)."""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("shared", "0001_app_role_default_privileges")]
    operations = [
        migrations.CreateModel(
            name="ScopedProbe",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("couple_id", models.UUIDField()),
                ("note", models.TextField()),
            ],
            options={"base_manager_name": "unscoped"},
        )
    ]

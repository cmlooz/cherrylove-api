"""Partitioned, append-only audit log (ADR-008 §1, §4, §5; REQ-F-LOG-03/04).

Raw SQL because the ORM does not create partitions. Runs as cherrylove_maintenance (migrations alias).
`audit_ensure_partitions(months_ahead)` creates the current month and the next ones; the daily maintenance job
(F8.3) calls the same function, so every partition gets the same privileges and indexes.
"""

from __future__ import annotations

from django.db import migrations

APP_ROLE = "cherrylove_app"

FORWARD = f"""
CREATE TABLE audit_event (
    id uuid NOT NULL,
    occurred_at timestamptz NOT NULL,
    request_id text,
    actor_type text NOT NULL CHECK (actor_type IN ('partner', 'staff', 'system', 'anonymous')),
    actor_id uuid,
    couple_id uuid,
    action text NOT NULL CHECK (action ~ '^[a-z_]+\\.[a-z_]+$'),
    outcome text NOT NULL CHECK (outcome IN ('success', 'rejected', 'failed')),
    entity_type text,
    entity_id uuid,
    ip inet,
    device jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    changes jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

-- Partitioned indexes: every partition, present and future, gets its own copy (ADR-008 §5).
CREATE INDEX audit_event_couple_idx ON audit_event (couple_id, occurred_at);
CREATE INDEX audit_event_actor_idx ON audit_event (actor_id, occurred_at);
CREATE INDEX audit_event_action_idx ON audit_event (action, occurred_at);

-- Append-only, first barrier: the app role may only add and read rows (ADR-008 §4).
REVOKE ALL ON audit_event FROM {APP_ROLE};
GRANT INSERT, SELECT ON audit_event TO {APP_ROLE};

-- Second barrier: no role, maintenance included, may change or delete a row. Retention drops partitions.
CREATE FUNCTION audit_event_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_event is append-only (ADR-008 §4): % refused', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;
CREATE TRIGGER audit_event_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_event
    FOR EACH ROW EXECUTE FUNCTION audit_event_append_only();
CREATE TRIGGER audit_event_no_truncate
    BEFORE TRUNCATE ON audit_event
    FOR EACH STATEMENT EXECUTE FUNCTION audit_event_append_only();

-- Monthly UTC partitions: the current month plus `months_ahead`. Idempotent.
CREATE FUNCTION audit_ensure_partitions(months_ahead integer) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    month_start timestamptz;
    partition_name text;
BEGIN
    FOR offset_months IN 0..months_ahead LOOP
        month_start := date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
            + make_interval(months => offset_months);
        partition_name := format('audit_event_y%sm%s',
            to_char(month_start AT TIME ZONE 'UTC', 'YYYY'), to_char(month_start AT TIME ZONE 'UTC', 'MM'));
        IF to_regclass(partition_name) IS NULL THEN
            EXECUTE format('CREATE TABLE %I PARTITION OF audit_event FOR VALUES FROM (%L) TO (%L)',
                partition_name, month_start, month_start + interval '1 month');
            -- Partitions are reached only through the parent, never directly.
            EXECUTE format('REVOKE ALL ON %I FROM {APP_ROLE}', partition_name);
        END IF;
    END LOOP;
END;
$$;

SELECT audit_ensure_partitions(3);
"""

BACKWARD = """
DROP TABLE audit_event;
DROP FUNCTION audit_ensure_partitions(integer);
DROP FUNCTION audit_event_append_only();
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = [("shared", "0001_app_role_default_privileges")]
    operations = [migrations.RunSQL(FORWARD, BACKWARD)]

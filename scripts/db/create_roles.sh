#!/bin/sh
# Creates the two database roles (ADR-008 §4, DATA-001 §3). Run once per cluster as a superuser:
# by the postgres image's initdb in compose.yaml, and by CI before migrations.
# Connection uses libpq env vars (PGHOST, PGUSER, ...); passwords come from the environment (DEC-039).
#   APP_DB_PASSWORD, MAINTENANCE_DB_PASSWORD  required
#   POSTGRES_DB                               database the maintenance role will own (default cherrylove)
set -eu

psql -v ON_ERROR_STOP=1 \
  -v db="${POSTGRES_DB:-cherrylove}" \
  -v app_password="$APP_DB_PASSWORD" \
  -v maintenance_password="$MAINTENANCE_DB_PASSWORD" \
  --dbname "${POSTGRES_DB:-cherrylove}" <<'SQL'
SELECT format('CREATE ROLE cherrylove_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cherrylove_app') \gexec

-- CREATEDB lets the test runner create its throwaway database as the DDL role.
SELECT format('CREATE ROLE cherrylove_maintenance LOGIN CREATEDB PASSWORD %L', :'maintenance_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cherrylove_maintenance') \gexec

-- The maintenance role owns the database, hence its `public` schema (pg_database_owner) and all DDL.
-- The app role keeps only CONNECT and USAGE (PostgreSQL 15+ defaults); DML comes from default
-- privileges set by the first migration.
ALTER DATABASE :"db" OWNER TO cherrylove_maintenance;
SQL

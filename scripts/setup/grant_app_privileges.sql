-- Grant the application role the privileges it needs, and nothing more.
--
-- The app connects as shiksha_app rather than the postgres superuser. That is
-- right, but the role was created without any table grants at all — it had
-- USAGE on the schema and zero privileges on all 42 tables, so every query the
-- API made failed with "permission denied". Route registration still succeeded,
-- which is why it looked fine.
--
-- What the app gets: DML on tables, sequence usage for generated ids.
-- What it does not get: CREATE, DROP, ALTER, TRUNCATE, or ownership. Migrations
-- run as the owner (postgres); the app never changes its own schema.
--
-- Run as the database owner:
--     psql -d shiksha_setu -f scripts/setup/grant_app_privileges.sql
--
-- Re-runnable.

\set app_role shiksha_app

-- Connect and see the schema.
GRANT CONNECT ON DATABASE shiksha_setu TO :app_role;
GRANT USAGE ON SCHEMA public TO :app_role;

-- Read and write rows in every existing table.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :app_role;

-- Sequences back the identity columns; without USAGE, INSERT fails on any
-- table with a serial primary key even though INSERT itself was granted.
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :app_role;

-- Tables created by future migrations would otherwise arrive ungranted and
-- reproduce the original problem one migration later.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :app_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO :app_role;

-- alembic_version stays read-only: the app may check which migration it is
-- running against, but only the migration runner may move it.
REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM :app_role;

-- PostgreSQL 14 and earlier grant CREATE on the public schema to PUBLIC, so
-- every role — including the application — can create tables. That undoes
-- most of the point of a restricted app role. PostgreSQL 15 changed the
-- default; this applies the same hardening here.
--
-- The database owner keeps CREATE through ownership, so migrations are
-- unaffected.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

\echo 'Granted. Verifying:'
SELECT
    count(DISTINCT table_name) AS tables_readable
FROM information_schema.role_table_grants
WHERE grantee = 'shiksha_app' AND privilege_type = 'SELECT';

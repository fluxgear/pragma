\set ON_ERROR_STOP on

\echo 'Verifying PostgreSQL 18 and extension availability in application database'
DO $$
BEGIN
    IF current_setting('server_version_num')::integer < 180000 THEN
        RAISE EXCEPTION 'Pragma Docker requires PostgreSQL 18 or newer; found server_version_num=%', current_setting('server_version_num');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_trgm') THEN
        RAISE EXCEPTION 'Required PostgreSQL extension pg_trgm is not available in this image';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
        RAISE EXCEPTION 'Required PostgreSQL extension vector/pgvector is not available in this image';
    END IF;
END;
$$;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

\connect template1

\echo 'Verifying PostgreSQL 18 and extension availability in template1'
DO $$
BEGIN
    IF current_setting('server_version_num')::integer < 180000 THEN
        RAISE EXCEPTION 'Pragma Docker requires PostgreSQL 18 or newer; found server_version_num=%', current_setting('server_version_num');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_trgm') THEN
        RAISE EXCEPTION 'Required PostgreSQL extension pg_trgm is not available in this image';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
        RAISE EXCEPTION 'Required PostgreSQL extension vector/pgvector is not available in this image';
    END IF;
END;
$$;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

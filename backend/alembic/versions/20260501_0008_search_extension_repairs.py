# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Repair optional search extension artifacts when extensions appear later."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260501_0008'
down_revision = '20260427_0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Repair optional search schema artifacts idempotently."""

    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.pragma_search_documents') IS NOT NULL
               AND EXISTS (
                   SELECT 1
                   FROM pg_available_extensions
                   WHERE name = 'pg_trgm'
                     AND installed_version IS NOT NULL
               )
               AND to_regclass('public.ix_pragma_search_documents_search_text_trgm')
                   IS NULL
            THEN
                CREATE INDEX ix_pragma_search_documents_search_text_trgm
                ON public.pragma_search_documents
                USING gin (search_text_normalized gin_trgm_ops);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.pragma_search_documents') IS NOT NULL
               AND EXISTS (
                   SELECT 1
                   FROM pg_available_extensions
                   WHERE name = 'vector'
                     AND installed_version IS NOT NULL
               )
               AND NOT EXISTS (
                   SELECT 1
                   FROM information_schema.columns
                   WHERE table_schema = 'public'
                     AND table_name = 'pragma_search_documents'
                     AND column_name = 'embedding'
               )
            THEN
                EXECUTE 'ALTER TABLE public.pragma_search_documents '
                    || 'ADD COLUMN embedding vector NULL';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Leave repaired search artifacts in place on downgrade."""

    # Non-destructive repair migration: downgrade intentionally does not remove
    # search artifacts that earlier migrations may have created legitimately.

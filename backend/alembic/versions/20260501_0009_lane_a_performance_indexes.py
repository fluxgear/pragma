# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Add Lane A performance indexes for content lists and vector search."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260501_0009'
down_revision = '20260501_0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create idempotent performance indexes for hot DB/search paths."""

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pragma_content_entries_updated_at
        ON public.pragma_content_entries (updated_at DESC, id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pragma_content_entries_status_updated_at
        ON public.pragma_content_entries (status, updated_at DESC, id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pragma_content_entries_content_type_status_updated_at
        ON public.pragma_content_entries (content_type_id, status, updated_at DESC, id DESC)
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
               AND EXISTS (
                   SELECT 1
                   FROM information_schema.columns
                   WHERE table_schema = 'public'
                     AND table_name = 'pragma_search_documents'
                     AND column_name = 'embedding'
               )
               AND EXISTS (
                   SELECT 1
                   FROM pg_attribute AS a
                   JOIN pg_class AS c ON c.oid = a.attrelid
                   JOIN pg_namespace AS n ON n.oid = c.relnamespace
                   WHERE n.nspname = 'public'
                     AND c.relname = 'pragma_search_documents'
                     AND a.attname = 'embedding'
                     AND a.atttypmod > 0
               )
               AND EXISTS (
                   SELECT 1
                   FROM pg_am
                   WHERE amname = 'hnsw'
               )
               AND EXISTS (
                   SELECT 1
                   FROM pg_opclass
                   WHERE opcname = 'vector_cosine_ops'
               )
               AND to_regclass('public.ix_pragma_search_documents_embedding_hnsw')
                   IS NULL
            THEN
                CREATE INDEX ix_pragma_search_documents_embedding_hnsw
                ON public.pragma_search_documents
                USING hnsw (embedding vector_cosine_ops)
                WHERE embedding IS NOT NULL;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Drop Lane A performance indexes."""

    op.execute('DROP INDEX IF EXISTS public.ix_pragma_search_documents_embedding_hnsw')
    op.execute(
        'DROP INDEX IF EXISTS public.ix_pragma_content_entries_content_type_status_updated_at'
    )
    op.execute('DROP INDEX IF EXISTS public.ix_pragma_content_entries_status_updated_at')
    op.execute('DROP INDEX IF EXISTS public.ix_pragma_content_entries_updated_at')

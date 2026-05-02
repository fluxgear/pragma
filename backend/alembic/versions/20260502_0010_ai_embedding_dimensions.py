# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Add configured embedding dimensions for fixed pgvector indexes."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260502_0010'
down_revision = '20260501_0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add embedding dimension settings and repair fixed vector schema."""

    op.add_column(
        'pragma_ai_provider_settings',
        sa.Column('embedding_dimensions', sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        'ck_pragma_ai_provider_settings_embedding_dimensions',
        'pragma_ai_provider_settings',
        'embedding_dimensions BETWEEN 1 AND 2000',
    )
    op.execute(
        """
        DO $$
        DECLARE
            configured_dimensions integer;
        BEGIN
            SELECT embedding_dimensions
            INTO configured_dimensions
            FROM public.pragma_ai_provider_settings
            WHERE id = 1
              AND embedding_dimensions BETWEEN 1 AND 2000;

            IF configured_dimensions IS NOT NULL
               AND to_regclass('public.pragma_search_documents') IS NOT NULL
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
            THEN
                DROP INDEX IF EXISTS public.ix_pragma_search_documents_embedding_hnsw;
                UPDATE public.pragma_search_documents
                SET
                    embedding = NULL,
                    embedding_provider = NULL,
                    embedding_model = NULL,
                    embedding_updated_at = NULL
                WHERE embedding IS NOT NULL
                   OR embedding_provider IS NOT NULL
                   OR embedding_model IS NOT NULL
                   OR embedding_updated_at IS NOT NULL;
                EXECUTE format(
                    'ALTER TABLE public.pragma_search_documents '
                    || 'ALTER COLUMN embedding TYPE vector(%s) '
                    || 'USING NULL::vector(%s)',
                    configured_dimensions,
                    configured_dimensions
                );
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
                     AND NOT a.attisdropped
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
    """Remove embedding dimension settings and fixed-vector-only HNSW index."""

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
            THEN
                DROP INDEX IF EXISTS public.ix_pragma_search_documents_embedding_hnsw;
                ALTER TABLE public.pragma_search_documents
                ALTER COLUMN embedding TYPE vector
                USING embedding::vector;
            END IF;
        END
        $$;
        """
    )
    op.drop_constraint(
        'ck_pragma_ai_provider_settings_embedding_dimensions',
        'pragma_ai_provider_settings',
        type_='check',
    )
    op.drop_column('pragma_ai_provider_settings', 'embedding_dimensions')

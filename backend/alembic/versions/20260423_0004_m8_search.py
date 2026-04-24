# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
'''Create the M8 search schema and derived indexes.

Args:
    None.

Returns:
    None.

Raises:
    None.
'''

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260423_0004'
down_revision = '20260421_0003'
branch_labels = None
depends_on = None


def _extension_installed(extension_name: str) -> bool:
    '''Return whether a PostgreSQL extension is installed in this database.

    Args:
        extension_name: PostgreSQL extension name.

    Returns:
        bool: True when the extension is installed.

    Raises:
        sqlalchemy.exc.DatabaseError: If the capability query fails.
    '''

    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            '''
            SELECT EXISTS (
                SELECT 1
                FROM pg_available_extensions
                WHERE name = :extension_name
                  AND installed_version IS NOT NULL
            ) AS installed
            '''
        ),
        {'extension_name': extension_name},
    ).mappings().one()
    return bool(row['installed'])


def _backfill_search_documents() -> None:
    '''Populate derived search documents from existing published content.

    Args:
        None.

    Returns:
        None.

    Raises:
        sqlalchemy.exc.DatabaseError: If the backfill query fails.
    '''

    op.execute(
        '''
        WITH entry_source AS (
            SELECT
                e.id AS entry_id,
                e.content_type_id,
                ct.slug AS content_type_slug,
                e.slug AS entry_slug,
                e.payload,
                COALESCE(e.published_at, e.updated_at) AS published_at,
                e.updated_at
            FROM pragma_content_entries AS e
            JOIN pragma_content_types AS ct ON ct.id = e.content_type_id
            WHERE e.status = 'published'
        ),
        field_values AS (
            SELECT
                es.entry_id,
                f.name AS field_name,
                f.position,
                trim(
                    regexp_replace(
                        CASE
                            WHEN f.field_type = 'rich_text'
                            THEN regexp_replace(
                                es.payload ->> f.name,
                                '<[^>]+>',
                                ' ',
                                'g'
                            )
                            ELSE es.payload ->> f.name
                        END,
                        '[[:space:]]+',
                        ' ',
                        'g'
                    )
                ) AS field_value
            FROM entry_source AS es
            JOIN pragma_content_fields AS f ON f.content_type_id = es.content_type_id
            WHERE f.field_type IN ('text', 'long_text', 'rich_text')
              AND jsonb_typeof(es.payload -> f.name) = 'string'
        ),
        field_aggregates AS (
            SELECT
                es.entry_id,
                es.content_type_id,
                es.content_type_slug,
                es.entry_slug,
                es.payload,
                es.published_at,
                es.updated_at,
                COALESCE(
                    array_agg(field_values.field_name ORDER BY field_values.position)
                        FILTER (WHERE field_values.field_value <> ''),
                    ARRAY[]::text[]
                ) AS searchable_field_names,
                array_agg(field_values.field_value ORDER BY field_values.position)
                    FILTER (WHERE field_values.field_value <> '') AS searchable_values,
                array_agg(field_values.field_value ORDER BY field_values.position)
                    FILTER (
                        WHERE field_values.field_value <> ''
                          AND field_values.field_name NOT IN ('title', 'name')
                    ) AS body_values
            FROM entry_source AS es
            LEFT JOIN field_values ON field_values.entry_id = es.entry_id
            GROUP BY
                es.entry_id,
                es.content_type_id,
                es.content_type_slug,
                es.entry_slug,
                es.payload,
                es.published_at,
                es.updated_at
        ),
        search_source AS (
            SELECT
                field_aggregates.entry_id,
                field_aggregates.content_type_id,
                field_aggregates.content_type_slug,
                field_aggregates.entry_slug,
                COALESCE(
                    NULLIF(preferred.title_text, ''),
                    NULLIF(preferred.name_text, ''),
                    left(field_aggregates.searchable_values[1], 160),
                    field_aggregates.entry_slug
                ) AS title_text,
                COALESCE(
                    NULLIF(array_to_string(field_aggregates.body_values, ' '), ''),
                    field_aggregates.searchable_values[1],
                    ''
                ) AS body_text,
                field_aggregates.searchable_field_names,
                field_aggregates.published_at,
                field_aggregates.updated_at
            FROM field_aggregates
            CROSS JOIN LATERAL (
                SELECT
                    trim(
                        regexp_replace(
                            CASE
                                WHEN jsonb_typeof(field_aggregates.payload -> 'title') = 'string'
                                 AND strpos(field_aggregates.payload ->> 'title', '<') > 0
                                THEN regexp_replace(
                                    field_aggregates.payload ->> 'title',
                                    '<[^>]+>',
                                    ' ',
                                    'g'
                                )
                                WHEN jsonb_typeof(field_aggregates.payload -> 'title') = 'string'
                                THEN field_aggregates.payload ->> 'title'
                            END,
                            '[[:space:]]+',
                            ' ',
                            'g'
                        )
                    ) AS title_text,
                    trim(
                        regexp_replace(
                            CASE
                                WHEN jsonb_typeof(field_aggregates.payload -> 'name') = 'string'
                                 AND strpos(field_aggregates.payload ->> 'name', '<') > 0
                                THEN regexp_replace(
                                    field_aggregates.payload ->> 'name',
                                    '<[^>]+>',
                                    ' ',
                                    'g'
                                )
                                WHEN jsonb_typeof(field_aggregates.payload -> 'name') = 'string'
                                THEN field_aggregates.payload ->> 'name'
                            END,
                            '[[:space:]]+',
                            ' ',
                            'g'
                        )
                    ) AS name_text
            ) AS preferred
        )
        INSERT INTO pragma_search_documents (
            entry_id,
            content_type_id,
            content_type_slug,
            entry_slug,
            title_text,
            body_text,
            search_text_normalized,
            searchable_field_names,
            search_tsv,
            published_at,
            updated_at
        )
        SELECT
            entry_id,
            content_type_id,
            content_type_slug,
            entry_slug,
            title_text,
            body_text,
            lower(
                trim(
                    regexp_replace(
                        concat_ws(' ', title_text, body_text),
                        '[[:space:]]+',
                        ' ',
                        'g'
                    )
                )
            ) AS search_text_normalized,
            searchable_field_names,
            setweight(to_tsvector('simple', title_text), 'A')
                || setweight(to_tsvector('simple', body_text), 'B') AS search_tsv,
            published_at,
            updated_at
        FROM search_source
        '''
    )


def upgrade() -> None:
    '''Create the schema required by the M8 search foundation.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    '''

    pg_trgm_installed = _extension_installed('pg_trgm')
    vector_installed = _extension_installed('vector')

    op.create_table(
        'pragma_search_documents',
        sa.Column('entry_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('content_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_type_slug', sa.String(length=160), nullable=False),
        sa.Column('entry_slug', sa.String(length=160), nullable=False),
        sa.Column('title_text', sa.Text(), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=False),
        sa.Column('search_text_normalized', sa.Text(), nullable=False),
        sa.Column(
            'searchable_field_names',
            postgresql.ARRAY(sa.Text()),
            nullable=False,
        ),
        sa.Column('search_tsv', postgresql.TSVECTOR(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['entry_id'], ['pragma_content_entries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['content_type_id'], ['pragma_content_types.id'], ondelete='CASCADE'
        ),
    )
    if vector_installed:
        op.execute('ALTER TABLE pragma_search_documents ADD COLUMN embedding vector NULL')
    op.create_index(
        'ix_pragma_search_documents_published_at',
        'pragma_search_documents',
        ['published_at'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_search_documents_content_type_slug_published_at',
        'pragma_search_documents',
        ['content_type_slug', 'published_at'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_search_documents_search_tsv',
        'pragma_search_documents',
        ['search_tsv'],
        unique=False,
        postgresql_using='gin',
    )
    if pg_trgm_installed:
        op.execute(
            '''
            CREATE INDEX ix_pragma_search_documents_search_text_trgm
            ON pragma_search_documents
            USING gin (search_text_normalized gin_trgm_ops)
            '''
        )

    _backfill_search_documents()


def downgrade() -> None:
    '''Drop the schema required by the M8 search foundation.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    '''

    op.execute('DROP INDEX IF EXISTS ix_pragma_search_documents_search_text_trgm')
    op.drop_index(
        'ix_pragma_search_documents_search_tsv', table_name='pragma_search_documents'
    )
    op.drop_index(
        'ix_pragma_search_documents_content_type_slug_published_at',
        table_name='pragma_search_documents',
    )
    op.drop_index(
        'ix_pragma_search_documents_published_at', table_name='pragma_search_documents'
    )
    op.drop_table('pragma_search_documents')

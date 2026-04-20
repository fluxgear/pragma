# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Create M2 content engine tables and indexes.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260420_0002'
down_revision = '20260420_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the schema required by the M2 content engine.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    op.create_table(
        'pragma_content_types',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'], ['pragma_users.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['updated_by_user_id'], ['pragma_users.id'], ondelete='SET NULL'
        ),
    )
    op.create_index('ix_pragma_content_types_slug', 'pragma_content_types', ['slug'], unique=True)
    op.create_index(
        'ix_pragma_content_types_updated_at',
        'pragma_content_types',
        ['updated_at'],
        unique=False,
    )

    op.create_table(
        'pragma_content_fields',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('content_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('field_type', sa.String(length=32), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('config', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            (
                "field_type IN ('text', 'long_text', 'rich_text', 'integer', 'number', "
                "'boolean', 'date', 'datetime', 'json')"
            ),
            name='ck_pragma_content_fields_field_type',
        ),
        sa.ForeignKeyConstraint(
            ['content_type_id'],
            ['pragma_content_types.id'],
            ondelete='CASCADE',
        ),
    )
    op.create_index(
        'ix_pragma_content_fields_content_type_name',
        'pragma_content_fields',
        ['content_type_id', 'name'],
        unique=True,
    )
    op.create_index(
        'ix_pragma_content_fields_content_type_position',
        'pragma_content_fields',
        ['content_type_id', 'position'],
        unique=False,
    )

    op.create_table(
        'pragma_content_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('content_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('slug', sa.String(length=160), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name='ck_pragma_content_entries_status',
        ),
        sa.ForeignKeyConstraint(
            ['content_type_id'],
            ['pragma_content_types.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'], ['pragma_users.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['updated_by_user_id'], ['pragma_users.id'], ondelete='SET NULL'
        ),
    )
    op.create_index(
        'ix_pragma_content_entries_content_type_slug',
        'pragma_content_entries',
        ['content_type_id', 'slug'],
        unique=True,
    )
    op.create_index(
        'ix_pragma_content_entries_content_type_status',
        'pragma_content_entries',
        ['content_type_id', 'status'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_content_entries_content_type_updated_at',
        'pragma_content_entries',
        ['content_type_id', 'updated_at'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_content_entries_created_at',
        'pragma_content_entries',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_content_entries_published_at',
        'pragma_content_entries',
        ['published_at'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_content_entries_payload',
        'pragma_content_entries',
        ['payload'],
        unique=False,
        postgresql_using='gin',
    )


def downgrade() -> None:
    """Drop the schema required by the M2 content engine.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    op.drop_index('ix_pragma_content_entries_payload', table_name='pragma_content_entries')
    op.drop_index('ix_pragma_content_entries_published_at', table_name='pragma_content_entries')
    op.drop_index('ix_pragma_content_entries_created_at', table_name='pragma_content_entries')
    op.drop_index(
        'ix_pragma_content_entries_content_type_updated_at',
        table_name='pragma_content_entries',
    )
    op.drop_index(
        'ix_pragma_content_entries_content_type_status',
        table_name='pragma_content_entries',
    )
    op.drop_index(
        'ix_pragma_content_entries_content_type_slug',
        table_name='pragma_content_entries',
    )
    op.drop_table('pragma_content_entries')

    op.drop_index(
        'ix_pragma_content_fields_content_type_position',
        table_name='pragma_content_fields',
    )
    op.drop_index(
        'ix_pragma_content_fields_content_type_name',
        table_name='pragma_content_fields',
    )
    op.drop_table('pragma_content_fields')

    op.drop_index('ix_pragma_content_types_updated_at', table_name='pragma_content_types')
    op.drop_index('ix_pragma_content_types_slug', table_name='pragma_content_types')
    op.drop_table('pragma_content_types')

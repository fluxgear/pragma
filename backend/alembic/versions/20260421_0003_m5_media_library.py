# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Create M5 media library tables and indexes.

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
revision = '20260421_0003'
down_revision = '20260420_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the schema required by the M5 media library.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    op.create_table(
        'pragma_media_assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('mime_type', sa.String(length=255), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('alt_text', sa.String(length=255), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'variants',
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column('uploader_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            'size_bytes >= 0',
            name='ck_pragma_media_assets_size_bytes_nonnegative',
        ),
        sa.CheckConstraint(
            'width IS NULL OR width > 0',
            name='ck_pragma_media_assets_width_positive',
        ),
        sa.CheckConstraint(
            'height IS NULL OR height > 0',
            name='ck_pragma_media_assets_height_positive',
        ),
        sa.ForeignKeyConstraint(['uploader_user_id'], ['pragma_users.id'], ondelete='SET NULL'),
    )
    op.create_index(
        'ix_pragma_media_assets_storage_key',
        'pragma_media_assets',
        ['storage_key'],
        unique=True,
    )
    op.create_index(
        'ix_pragma_media_assets_updated_at',
        'pragma_media_assets',
        ['updated_at'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_media_assets_mime_type_updated_at',
        'pragma_media_assets',
        ['mime_type', 'updated_at'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_media_assets_uploader_updated_at',
        'pragma_media_assets',
        ['uploader_user_id', 'updated_at'],
        unique=False,
    )


def downgrade() -> None:
    """Drop the schema required by the M5 media library.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    op.drop_index('ix_pragma_media_assets_uploader_updated_at', table_name='pragma_media_assets')
    op.drop_index('ix_pragma_media_assets_mime_type_updated_at', table_name='pragma_media_assets')
    op.drop_index('ix_pragma_media_assets_updated_at', table_name='pragma_media_assets')
    op.drop_index('ix_pragma_media_assets_storage_key', table_name='pragma_media_assets')
    op.drop_table('pragma_media_assets')

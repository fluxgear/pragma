# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Create M9 AI-provider settings and search embedding metadata schema.

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
revision = '20260426_0005'
down_revision = '20260423_0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create schema additions required by M9 AI integration.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    op.create_table(
        'pragma_ai_provider_settings',
        sa.Column(
            'id',
            sa.SmallInteger(),
            primary_key=True,
            nullable=False,
            server_default=sa.text('1'),
        ),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('provider', sa.String(length=32), nullable=True),
        sa.Column('base_url', sa.String(length=500), nullable=True),
        sa.Column('api_key', sa.String(length=500), nullable=True),
        sa.Column('embedding_model', sa.String(length=200), nullable=True),
        sa.Column(
            'request_timeout_seconds',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('15'),
        ),
        sa.Column('updated_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('id = 1', name='ck_pragma_ai_provider_settings_singleton'),
        sa.ForeignKeyConstraint(
            ['updated_by_user_id'],
            ['pragma_users.id'],
            ondelete='SET NULL',
        ),
    )

    op.add_column(
        'pragma_search_documents',
        sa.Column('embedding_provider', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'pragma_search_documents',
        sa.Column('embedding_model', sa.String(length=200), nullable=True),
    )
    op.add_column(
        'pragma_search_documents',
        sa.Column('embedding_updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_pragma_search_documents_embedding_metadata',
        'pragma_search_documents',
        ['embedding_provider', 'embedding_model', 'embedding_updated_at'],
        unique=False,
    )


def downgrade() -> None:
    """Drop schema additions required by M9 AI integration.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    op.drop_index(
        'ix_pragma_search_documents_embedding_metadata',
        table_name='pragma_search_documents',
    )
    op.drop_column('pragma_search_documents', 'embedding_updated_at')
    op.drop_column('pragma_search_documents', 'embedding_model')
    op.drop_column('pragma_search_documents', 'embedding_provider')
    op.drop_table('pragma_ai_provider_settings')

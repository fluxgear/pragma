# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Add C5 theme settings singleton table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '20260507_0014'
down_revision = '20260507_0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create additive singleton theme settings storage."""

    op.create_table(
        'pragma_theme_settings',
        sa.Column('id', sa.SmallInteger(), nullable=False),
        sa.Column('active_theme_id', sa.String(length=64), nullable=True),
        sa.Column('design_settings', postgresql.JSONB(), nullable=False),
        sa.Column('updated_by_user_id', sa.Uuid(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint('id = 1', name='ck_pragma_theme_settings_singleton'),
        sa.CheckConstraint(
            "active_theme_id IS NULL OR active_theme_id ~ '^[a-z0-9][a-z0-9_-]{0,62}[a-z0-9]$'",
            name='ck_pragma_theme_settings_active_theme_id',
        ),
        sa.ForeignKeyConstraint(
            ['updated_by_user_id'],
            ['pragma_users.id'],
            name='fk_pragma_theme_settings_updated_by_user_id',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_pragma_theme_settings'),
    )


def downgrade() -> None:
    """Drop C5 theme settings storage."""

    op.drop_table('pragma_theme_settings')

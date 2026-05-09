# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Add dedicated AI provider secret storage table."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = '20260507_0015'
down_revision = '20260507_0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create additive secret storage path for AI provider credentials."""

    op.create_table(
        'pragma_ai_provider_secrets',
        sa.Column('settings_id', sa.SmallInteger(), nullable=False),
        sa.Column('api_key', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['settings_id'],
            ['pragma_ai_provider_settings.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('settings_id'),
    )

    op.execute(
        """
        INSERT INTO pragma_ai_provider_secrets (settings_id, api_key, created_at, updated_at)
        SELECT
            id,
            api_key,
            COALESCE(updated_at, CURRENT_TIMESTAMP),
            COALESCE(updated_at, CURRENT_TIMESTAMP)
        FROM pragma_ai_provider_settings
        WHERE api_key IS NOT NULL
          AND BTRIM(api_key) <> ''
        ON CONFLICT (settings_id) DO NOTHING
        """
    )


def downgrade() -> None:
    """Drop dedicated AI provider secret storage table."""

    op.drop_table('pragma_ai_provider_secrets')

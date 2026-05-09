# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Add C0.3 AI provider generation configuration columns."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = '20260507_0013'
down_revision = '20260506_0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add backward-compatible provider generation metadata columns."""

    op.add_column(
        'pragma_ai_provider_settings',
        sa.Column('display_name', sa.String(length=120), nullable=True),
    )
    op.add_column(
        'pragma_ai_provider_settings',
        sa.Column(
            'api_mode',
            sa.String(length=40),
            nullable=False,
            server_default='chat_completions',
        ),
    )
    op.add_column(
        'pragma_ai_provider_settings',
        sa.Column(
            'auth_mode',
            sa.String(length=40),
            nullable=False,
            server_default='api_key',
        ),
    )
    op.add_column(
        'pragma_ai_provider_settings',
        sa.Column('generation_model', sa.String(length=200), nullable=True),
    )
    op.add_column(
        'pragma_ai_provider_settings',
        sa.Column(
            'text_generation_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'pragma_ai_provider_settings',
        sa.Column(
            'editor_assist_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'pragma_ai_provider_settings',
        sa.Column(
            'seo_assist_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'pragma_ai_provider_settings',
        sa.Column('last_test_status', sa.String(length=40), nullable=True),
    )
    op.add_column(
        'pragma_ai_provider_settings',
        sa.Column('last_tested_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        'ck_pragma_ai_provider_settings_api_mode',
        'pragma_ai_provider_settings',
        "api_mode IN ('responses', 'chat_completions')",
    )
    op.create_check_constraint(
        'ck_pragma_ai_provider_settings_auth_mode',
        'pragma_ai_provider_settings',
        "auth_mode IN ('api_key', 'oauth')",
    )


def downgrade() -> None:
    """Drop C0.3 additive columns."""

    op.drop_constraint(
        'ck_pragma_ai_provider_settings_auth_mode',
        'pragma_ai_provider_settings',
        type_='check',
    )
    op.drop_constraint(
        'ck_pragma_ai_provider_settings_api_mode',
        'pragma_ai_provider_settings',
        type_='check',
    )
    for column_name in (
        'last_tested_at',
        'last_test_status',
        'seo_assist_enabled',
        'editor_assist_enabled',
        'text_generation_enabled',
        'generation_model',
        'auth_mode',
        'api_mode',
        'display_name',
    ):
        op.drop_column('pragma_ai_provider_settings', column_name)

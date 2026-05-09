# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Add C6 primary navigation persistence."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '20260507_0017'
down_revision = '20260507_0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create additive navigation menu tables."""

    target_shape_constraint = (
        "(link_type = 'content_entry' "
        "AND content_entry_id IS NOT NULL "
        "AND custom_url IS NULL) OR "
        "(link_type = 'custom_url' "
        "AND content_entry_id IS NULL "
        "AND custom_url IS NOT NULL)"
    )

    op.create_table(
        'pragma_navigation_menus',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(length=32), nullable=False),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "key IN ('primary')",
            name='ck_pragma_navigation_menus_key',
        ),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'],
            ['pragma_users.id'],
            name='fk_pragma_navigation_menus_created_by_user_id',
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['updated_by_user_id'],
            ['pragma_users.id'],
            name='fk_pragma_navigation_menus_updated_by_user_id',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_pragma_navigation_menus'),
        sa.UniqueConstraint('key', name='uq_pragma_navigation_menus_key'),
    )

    op.create_table(
        'pragma_navigation_menu_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('menu_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=80), nullable=False),
        sa.Column('link_type', sa.String(length=16), nullable=False),
        sa.Column('content_entry_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('custom_url', sa.String(length=2048), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            'position >= 1',
            name='ck_pragma_navigation_menu_items_position_positive',
        ),
        sa.CheckConstraint(
            "link_type IN ('content_entry', 'custom_url')",
            name='ck_pragma_navigation_menu_items_link_type',
        ),
        sa.CheckConstraint(
            target_shape_constraint,
            name='ck_pragma_navigation_menu_items_target_shape',
        ),
        sa.ForeignKeyConstraint(
            ['menu_id'],
            ['pragma_navigation_menus.id'],
            name='fk_pragma_navigation_menu_items_menu_id',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['content_entry_id'],
            ['pragma_content_entries.id'],
            name='fk_pragma_navigation_menu_items_content_entry_id',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_pragma_navigation_menu_items'),
        sa.UniqueConstraint(
            'menu_id',
            'position',
            name='uq_pragma_navigation_menu_items_menu_position',
        ),
    )
    op.create_index(
        'ix_pragma_navigation_menu_items_menu_enabled_position',
        'pragma_navigation_menu_items',
        ['menu_id', 'enabled', 'position'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_navigation_menu_items_content_entry_id',
        'pragma_navigation_menu_items',
        ['content_entry_id'],
        unique=False,
    )


def downgrade() -> None:
    """Drop C6 navigation menu tables."""

    op.drop_index(
        'ix_pragma_navigation_menu_items_content_entry_id',
        table_name='pragma_navigation_menu_items',
    )
    op.drop_index(
        'ix_pragma_navigation_menu_items_menu_enabled_position',
        table_name='pragma_navigation_menu_items',
    )
    op.drop_table('pragma_navigation_menu_items')
    op.drop_table('pragma_navigation_menus')

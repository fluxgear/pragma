# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Add C6 nested navigation item support."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '20260511_0019'
down_revision = '20260511_0018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add parent pointers for nested navigation menus."""

    op.add_column(
        'pragma_navigation_menu_items',
        sa.Column('parent_item_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_pragma_navigation_menu_items_parent_item_id',
        'pragma_navigation_menu_items',
        'pragma_navigation_menu_items',
        ['parent_item_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.drop_constraint(
        'uq_pragma_navigation_menu_items_menu_position',
        'pragma_navigation_menu_items',
        type_='unique',
    )
    op.create_index(
        'ix_pragma_navigation_menu_items_parent_position',
        'pragma_navigation_menu_items',
        ['menu_id', 'parent_item_id', 'position'],
        unique=False,
    )


def downgrade() -> None:
    """Remove nested navigation parent pointers."""

    op.drop_index(
        'ix_pragma_navigation_menu_items_parent_position',
        table_name='pragma_navigation_menu_items',
    )
    op.create_unique_constraint(
        'uq_pragma_navigation_menu_items_menu_position',
        'pragma_navigation_menu_items',
        ['menu_id', 'position'],
    )
    op.drop_constraint(
        'fk_pragma_navigation_menu_items_parent_item_id',
        'pragma_navigation_menu_items',
        type_='foreignkey',
    )
    op.drop_column('pragma_navigation_menu_items', 'parent_item_id')

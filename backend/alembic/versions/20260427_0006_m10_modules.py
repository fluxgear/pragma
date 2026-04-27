# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Create M10 persisted module-state schema.

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
revision = '20260427_0006'
down_revision = '20260426_0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create schema additions required by M10 module lifecycle state.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    op.create_table(
        'pragma_modules',
        sa.Column('module_id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('updated_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['updated_by_user_id'],
            ['pragma_users.id'],
            ondelete='SET NULL',
        ),
    )
    op.create_index(
        'ix_pragma_modules_enabled',
        'pragma_modules',
        ['enabled'],
        unique=False,
    )


def downgrade() -> None:
    """Drop schema additions required by M10 module lifecycle state.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    op.drop_index('ix_pragma_modules_enabled', table_name='pragma_modules')
    op.drop_table('pragma_modules')

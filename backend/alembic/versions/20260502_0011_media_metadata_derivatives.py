# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Add media metadata for expanded upload support.

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

revision = '20260502_0011'
down_revision = '20260502_0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add JSON metadata storage to media assets."""

    op.add_column(
        'pragma_media_assets',
        sa.Column(
            'metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='{}',
        ),
    )


def downgrade() -> None:
    """Remove JSON metadata storage from media assets."""

    op.drop_column('pragma_media_assets', 'metadata')

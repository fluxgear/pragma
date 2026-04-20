# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Create M1 auth and install baseline tables.

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
revision = "20260420_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the baseline schema required by M1.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    op.create_table(
        "pragma_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pragma_users_email", "pragma_users", ["email"], unique=True)
    op.create_index("ix_pragma_users_username", "pragma_users", ["username"], unique=True)

    op.create_table(
        "pragma_install_state",
        sa.Column(
            "id",
            sa.SmallInteger(),
            primary_key=True,
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("is_installed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("installed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("id = 1", name="ck_pragma_install_state_singleton"),
        sa.ForeignKeyConstraint(
            ["installed_by_user_id"],
            ["pragma_users.id"],
            ondelete="SET NULL",
        ),
    )

    op.create_table(
        "pragma_refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_from_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["pragma_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["rotated_from_id"],
            ["pragma_refresh_tokens.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_pragma_refresh_tokens_user_id",
        "pragma_refresh_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_pragma_refresh_tokens_token_hash",
        "pragma_refresh_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_pragma_refresh_tokens_expires_at",
        "pragma_refresh_tokens",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the baseline schema required by M1.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    op.drop_index("ix_pragma_refresh_tokens_expires_at", table_name="pragma_refresh_tokens")
    op.drop_index("ix_pragma_refresh_tokens_token_hash", table_name="pragma_refresh_tokens")
    op.drop_index("ix_pragma_refresh_tokens_user_id", table_name="pragma_refresh_tokens")
    op.drop_table("pragma_refresh_tokens")
    op.drop_table("pragma_install_state")
    op.drop_index("ix_pragma_users_username", table_name="pragma_users")
    op.drop_index("ix_pragma_users_email", table_name="pragma_users")
    op.drop_table("pragma_users")

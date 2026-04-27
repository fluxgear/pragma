# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Create M11 roles, permissions, and user-hardening schema.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260427_0007'
down_revision = '20260427_0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the schema required by M11 RBAC and account hardening.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    timestamp = datetime.now(tz=UTC)

    op.add_column(
        'pragma_users',
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'pragma_users',
        sa.Column(
            'force_password_change',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        """
        UPDATE pragma_users
        SET password_changed_at = created_at
        WHERE password_changed_at IS NULL
        """
    )

    op.create_table(
        'pragma_permissions',
        sa.Column('permission_key', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'pragma_roles',
        sa.Column('role_key', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'pragma_role_permissions',
        sa.Column('role_key', sa.String(length=64), nullable=False),
        sa.Column('permission_key', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['role_key'], ['pragma_roles.role_key'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['permission_key'],
            ['pragma_permissions.permission_key'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('role_key', 'permission_key'),
    )
    op.create_index(
        'ix_pragma_role_permissions_permission_key',
        'pragma_role_permissions',
        ['permission_key'],
        unique=False,
    )

    op.create_table(
        'pragma_user_roles',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_key', sa.String(length=64), nullable=False),
        sa.Column('assigned_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['pragma_users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_key'], ['pragma_roles.role_key'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['assigned_by_user_id'],
            ['pragma_users.id'],
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('user_id', 'role_key'),
    )
    op.create_index(
        'ix_pragma_user_roles_role_key',
        'pragma_user_roles',
        ['role_key'],
        unique=False,
    )
    op.create_index(
        'ix_pragma_user_roles_user_id',
        'pragma_user_roles',
        ['user_id'],
        unique=False,
    )

    permissions_table = sa.table(
        'pragma_permissions',
        sa.column('permission_key', sa.String(length=64)),
        sa.column('name', sa.String(length=120)),
        sa.column('description', sa.String(length=500)),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    roles_table = sa.table(
        'pragma_roles',
        sa.column('role_key', sa.String(length=64)),
        sa.column('name', sa.String(length=120)),
        sa.column('description', sa.String(length=500)),
        sa.column('is_system', sa.Boolean()),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    role_permissions_table = sa.table(
        'pragma_role_permissions',
        sa.column('role_key', sa.String(length=64)),
        sa.column('permission_key', sa.String(length=64)),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )

    permissions = (
        (
            'content.types.read',
            'Read content types',
            'View content-type definitions.',
        ),
        (
            'content.types.manage',
            'Manage content types',
            'Create, update, and delete content types.',
        ),
        ('content.entries.read', 'Read content entries', 'View content entries.'),
        (
            'content.entries.write',
            'Write content entries',
            'Create and update draft or archived content entries.',
        ),
        (
            'content.entries.publish',
            'Publish content entries',
            'Create or update published content entries.',
        ),
        ('content.entries.delete', 'Delete content entries', 'Delete content entries.'),
        ('media.assets.read', 'Read media assets', 'Browse and view media assets.'),
        ('media.assets.upload', 'Upload media assets', 'Upload new media assets.'),
        ('media.assets.delete', 'Delete media assets', 'Delete stored media assets.'),
        (
            'ai.settings.manage',
            'Manage AI settings',
            'View and update AI provider settings and maintenance actions.',
        ),
        (
            'modules.manage',
            'Manage modules',
            'View and update module lifecycle state.',
        ),
        (
            'users.manage',
            'Manage users',
            'Create and update user accounts plus role assignments.',
        ),
    )
    op.bulk_insert(
        permissions_table,
        [
            {
                'permission_key': key,
                'name': name,
                'description': description,
                'created_at': timestamp,
                'updated_at': timestamp,
            }
            for key, name, description in permissions
        ],
    )

    roles = (
        (
            'administrator',
            'Administrator',
            'Full product administration across users, AI, modules, content, and media.',
        ),
        (
            'editor',
            'Editor',
            'Manage content and media, including publishing.',
        ),
        (
            'author',
            'Author',
            'Create and update content drafts plus upload supporting media.',
        ),
        (
            'viewer',
            'Viewer',
            'Read-only authenticated access to content and media.',
        ),
    )
    op.bulk_insert(
        roles_table,
        [
            {
                'role_key': role_key,
                'name': name,
                'description': description,
                'is_system': True,
                'created_at': timestamp,
                'updated_at': timestamp,
            }
            for role_key, name, description in roles
        ],
    )

    role_permissions = (
        ('administrator', 'content.types.read'),
        ('administrator', 'content.types.manage'),
        ('administrator', 'content.entries.read'),
        ('administrator', 'content.entries.write'),
        ('administrator', 'content.entries.publish'),
        ('administrator', 'content.entries.delete'),
        ('administrator', 'media.assets.read'),
        ('administrator', 'media.assets.upload'),
        ('administrator', 'media.assets.delete'),
        ('administrator', 'ai.settings.manage'),
        ('administrator', 'modules.manage'),
        ('administrator', 'users.manage'),
        ('editor', 'content.types.read'),
        ('editor', 'content.types.manage'),
        ('editor', 'content.entries.read'),
        ('editor', 'content.entries.write'),
        ('editor', 'content.entries.publish'),
        ('editor', 'content.entries.delete'),
        ('editor', 'media.assets.read'),
        ('editor', 'media.assets.upload'),
        ('editor', 'media.assets.delete'),
        ('author', 'content.types.read'),
        ('author', 'content.entries.read'),
        ('author', 'content.entries.write'),
        ('author', 'media.assets.read'),
        ('author', 'media.assets.upload'),
        ('viewer', 'content.types.read'),
        ('viewer', 'content.entries.read'),
        ('viewer', 'media.assets.read'),
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {
                'role_key': role_key,
                'permission_key': permission_key,
                'created_at': timestamp,
            }
            for role_key, permission_key in role_permissions
        ],
    )

    op.execute(
        """
        INSERT INTO pragma_user_roles (user_id, role_key, assigned_by_user_id, created_at)
        SELECT id, 'administrator', NULL, created_at
        FROM pragma_users
        WHERE is_superuser = TRUE
        ON CONFLICT (user_id, role_key) DO NOTHING
        """
    )


def downgrade() -> None:
    """Drop the schema required by M11 RBAC and account hardening.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    op.drop_index('ix_pragma_user_roles_user_id', table_name='pragma_user_roles')
    op.drop_index('ix_pragma_user_roles_role_key', table_name='pragma_user_roles')
    op.drop_table('pragma_user_roles')
    op.drop_index('ix_pragma_role_permissions_permission_key', table_name='pragma_role_permissions')
    op.drop_table('pragma_role_permissions')
    op.drop_table('pragma_roles')
    op.drop_table('pragma_permissions')
    op.drop_column('pragma_users', 'force_password_change')
    op.drop_column('pragma_users', 'password_changed_at')

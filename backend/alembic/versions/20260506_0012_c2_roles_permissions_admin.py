# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Add C2 roles and permissions administration RBAC seed data.

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

from alembic import op

revision = '20260506_0012'
down_revision = '20260502_0011'
branch_labels = None
depends_on = None

_FROZEN_PERMISSIONS = (
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
        'Create, update, and administer user accounts and role assignments.',
    ),
    ('admin.access', 'Access admin', 'Access the administrative interface.'),
    (
        'roles.manage',
        'Manage roles',
        'Create, update, and administer role definitions and permissions.',
    ),
    ('themes.manage', 'Manage themes', 'Configure and administer themes.'),
    ('settings.manage', 'Manage settings', 'Configure site and product settings.'),
    (
        'page_builder.use',
        'Use page builder',
        'Use the page builder to assemble pages.',
    ),
    (
        'page_builder.design',
        'Design with page builder',
        'Design page builder layouts and reusable page patterns.',
    ),
    (
        'navigation.manage',
        'Manage navigation',
        'Configure site navigation menus and structure.',
    ),
    (
        'ai.editor_assist',
        'Use AI editor assist',
        'Use AI-assisted editing features.',
    ),
    (
        'ai.seo_assist',
        'Use AI SEO assist',
        'Use AI-assisted SEO metadata generation.',
    ),
    (
        'ai.oauth.manage',
        'Manage AI OAuth',
        'Manage AI provider OAuth authorization.',
    ),
)

_ADMINISTRATOR_PERMISSIONS = tuple(key for key, _name, _description in _FROZEN_PERMISSIONS)
_EDITOR_PERMISSIONS = (
    'content.types.read',
    'content.types.manage',
    'content.entries.read',
    'content.entries.write',
    'content.entries.publish',
    'content.entries.delete',
    'media.assets.read',
    'media.assets.upload',
    'media.assets.delete',
)
_AUTHOR_PERMISSIONS = (
    'content.types.read',
    'content.entries.read',
    'content.entries.write',
    'media.assets.read',
    'media.assets.upload',
)
_VIEWER_PERMISSIONS = (
    'content.types.read',
    'content.entries.read',
    'media.assets.read',
)
_FROZEN_ROLE_PERMISSIONS = (
    *(('administrator', permission_key) for permission_key in _ADMINISTRATOR_PERMISSIONS),
    *(('editor', permission_key) for permission_key in _EDITOR_PERMISSIONS),
    *(('author', permission_key) for permission_key in _AUTHOR_PERMISSIONS),
    *(('viewer', permission_key) for permission_key in _VIEWER_PERMISSIONS),
)


def upgrade() -> None:
    """Upsert frozen C2 permission rows and built-in role grants."""

    timestamp = datetime.now(tz=UTC)
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            INSERT INTO pragma_permissions (
                permission_key,
                name,
                description,
                created_at,
                updated_at
            )
            VALUES (
                :permission_key,
                :name,
                :description,
                :created_at,
                :updated_at
            )
            ON CONFLICT (permission_key) DO UPDATE
            SET name = EXCLUDED.name,
                description = EXCLUDED.description,
                updated_at = EXCLUDED.updated_at
            """
        ),
        [
            {
                'permission_key': key,
                'name': name,
                'description': description,
                'created_at': timestamp,
                'updated_at': timestamp,
            }
            for key, name, description in _FROZEN_PERMISSIONS
        ],
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO pragma_role_permissions (
                role_key,
                permission_key,
                created_at
            )
            VALUES (:role_key, :permission_key, :created_at)
            ON CONFLICT (role_key, permission_key) DO NOTHING
            """
        ),
        [
            {
                'role_key': role_key,
                'permission_key': permission_key,
                'created_at': timestamp,
            }
            for role_key, permission_key in _FROZEN_ROLE_PERMISSIONS
        ],
    )


def downgrade() -> None:
    """Leave additive RBAC seed rows in place on downgrade."""

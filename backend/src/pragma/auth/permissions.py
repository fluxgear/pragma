# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Central RBAC definitions and permission helpers for Pragma.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from pragma.errors import AuthError

PERMISSION_CONTENT_TYPES_READ = 'content.types.read'
PERMISSION_CONTENT_TYPES_MANAGE = 'content.types.manage'
PERMISSION_CONTENT_ENTRIES_READ = 'content.entries.read'
PERMISSION_CONTENT_ENTRIES_WRITE = 'content.entries.write'
PERMISSION_CONTENT_ENTRIES_PUBLISH = 'content.entries.publish'
PERMISSION_CONTENT_ENTRIES_DELETE = 'content.entries.delete'
PERMISSION_MEDIA_ASSETS_READ = 'media.assets.read'
PERMISSION_MEDIA_ASSETS_UPLOAD = 'media.assets.upload'
PERMISSION_MEDIA_ASSETS_DELETE = 'media.assets.delete'
PERMISSION_AI_SETTINGS_MANAGE = 'ai.settings.manage'
PERMISSION_MODULES_MANAGE = 'modules.manage'
PERMISSION_USERS_MANAGE = 'users.manage'
PERMISSION_ADMIN_ACCESS = 'admin.access'
PERMISSION_ROLES_MANAGE = 'roles.manage'
PERMISSION_THEMES_MANAGE = 'themes.manage'
PERMISSION_SETTINGS_MANAGE = 'settings.manage'
PERMISSION_PAGE_BUILDER_USE = 'page_builder.use'
PERMISSION_PAGE_BUILDER_DESIGN = 'page_builder.design'
PERMISSION_NAVIGATION_MANAGE = 'navigation.manage'
PERMISSION_AI_EDITOR_ASSIST = 'ai.editor_assist'
PERMISSION_AI_SEO_ASSIST = 'ai.seo_assist'
PERMISSION_AI_OAUTH_MANAGE = 'ai.oauth.manage'

ROLE_ADMINISTRATOR = 'administrator'
ROLE_EDITOR = 'editor'
ROLE_AUTHOR = 'author'
ROLE_VIEWER = 'viewer'


@dataclass(frozen=True)
class PermissionDefinition:
    """Immutable product permission definition.

    Args:
        key: Stable permission identifier.
        name: Human-readable permission label.
        description: Human-readable permission description.

    Returns:
        None.

    Raises:
        None.
    """

    key: str
    name: str
    description: str


@dataclass(frozen=True)
class RoleDefinition:
    """Immutable built-in role definition.

    Args:
        key: Stable role identifier.
        name: Human-readable role label.
        description: Human-readable role description.
        permissions: Ordered permission keys granted by the role.

    Returns:
        None.

    Raises:
        None.
    """

    key: str
    name: str
    description: str
    permissions: tuple[str, ...]


_PERMISSION_DEFINITIONS = (
    PermissionDefinition(
        key=PERMISSION_CONTENT_TYPES_READ,
        name='Read content types',
        description='View content-type definitions.',
    ),
    PermissionDefinition(
        key=PERMISSION_CONTENT_TYPES_MANAGE,
        name='Manage content types',
        description='Create, update, and delete content types.',
    ),
    PermissionDefinition(
        key=PERMISSION_CONTENT_ENTRIES_READ,
        name='Read content entries',
        description='View content entries.',
    ),
    PermissionDefinition(
        key=PERMISSION_CONTENT_ENTRIES_WRITE,
        name='Write content entries',
        description='Create and update draft or archived content entries.',
    ),
    PermissionDefinition(
        key=PERMISSION_CONTENT_ENTRIES_PUBLISH,
        name='Publish content entries',
        description='Create or update published content entries.',
    ),
    PermissionDefinition(
        key=PERMISSION_CONTENT_ENTRIES_DELETE,
        name='Delete content entries',
        description='Delete content entries.',
    ),
    PermissionDefinition(
        key=PERMISSION_MEDIA_ASSETS_READ,
        name='Read media assets',
        description='Browse and view media assets.',
    ),
    PermissionDefinition(
        key=PERMISSION_MEDIA_ASSETS_UPLOAD,
        name='Upload media assets',
        description='Upload new media assets.',
    ),
    PermissionDefinition(
        key=PERMISSION_MEDIA_ASSETS_DELETE,
        name='Delete media assets',
        description='Delete stored media assets.',
    ),
    PermissionDefinition(
        key=PERMISSION_AI_SETTINGS_MANAGE,
        name='Manage AI settings',
        description='View and update AI provider settings and maintenance actions.',
    ),
    PermissionDefinition(
        key=PERMISSION_MODULES_MANAGE,
        name='Manage modules',
        description='View and update module lifecycle state.',
    ),
    PermissionDefinition(
        key=PERMISSION_USERS_MANAGE,
        name='Manage users',
        description='Create, update, and administer user accounts and role assignments.',
    ),
    PermissionDefinition(
        key=PERMISSION_ADMIN_ACCESS,
        name='Access admin',
        description='Access the administrative interface.',
    ),
    PermissionDefinition(
        key=PERMISSION_ROLES_MANAGE,
        name='Manage roles',
        description='Create, update, and administer role definitions and permissions.',
    ),
    PermissionDefinition(
        key=PERMISSION_THEMES_MANAGE,
        name='Manage themes',
        description='Configure and administer themes.',
    ),
    PermissionDefinition(
        key=PERMISSION_SETTINGS_MANAGE,
        name='Manage settings',
        description='Configure site and product settings.',
    ),
    PermissionDefinition(
        key=PERMISSION_PAGE_BUILDER_USE,
        name='Use page builder',
        description='Use the page builder to assemble pages.',
    ),
    PermissionDefinition(
        key=PERMISSION_PAGE_BUILDER_DESIGN,
        name='Design with page builder',
        description='Design page builder layouts and reusable page patterns.',
    ),
    PermissionDefinition(
        key=PERMISSION_NAVIGATION_MANAGE,
        name='Manage navigation',
        description='Configure site navigation menus and structure.',
    ),
    PermissionDefinition(
        key=PERMISSION_AI_EDITOR_ASSIST,
        name='Use AI editor assist',
        description='Use AI-assisted editing features.',
    ),
    PermissionDefinition(
        key=PERMISSION_AI_SEO_ASSIST,
        name='Use AI SEO assist',
        description='Use AI-assisted SEO metadata generation.',
    ),
    PermissionDefinition(
        key=PERMISSION_AI_OAUTH_MANAGE,
        name='Manage AI OAuth',
        description='Manage AI provider OAuth authorization.',
    ),
)

_PERMISSION_KEYS = tuple(permission.key for permission in _PERMISSION_DEFINITIONS)

_ROLE_DEFINITIONS = (
    RoleDefinition(
        key=ROLE_ADMINISTRATOR,
        name='Administrator',
        description='Full product administration across users, AI, modules, content, and media.',
        permissions=_PERMISSION_KEYS,
    ),
    RoleDefinition(
        key=ROLE_EDITOR,
        name='Editor',
        description='Manage content and media, including publishing.',
        permissions=(
            PERMISSION_CONTENT_TYPES_READ,
            PERMISSION_CONTENT_TYPES_MANAGE,
            PERMISSION_CONTENT_ENTRIES_READ,
            PERMISSION_CONTENT_ENTRIES_WRITE,
            PERMISSION_CONTENT_ENTRIES_PUBLISH,
            PERMISSION_CONTENT_ENTRIES_DELETE,
            PERMISSION_MEDIA_ASSETS_READ,
            PERMISSION_MEDIA_ASSETS_UPLOAD,
            PERMISSION_MEDIA_ASSETS_DELETE,
        ),
    ),
    RoleDefinition(
        key=ROLE_AUTHOR,
        name='Author',
        description='Create and update content drafts plus upload supporting media.',
        permissions=(
            PERMISSION_CONTENT_TYPES_READ,
            PERMISSION_CONTENT_ENTRIES_READ,
            PERMISSION_CONTENT_ENTRIES_WRITE,
            PERMISSION_MEDIA_ASSETS_READ,
            PERMISSION_MEDIA_ASSETS_UPLOAD,
        ),
    ),
    RoleDefinition(
        key=ROLE_VIEWER,
        name='Viewer',
        description='Read-only authenticated access to content and media.',
        permissions=(
            PERMISSION_CONTENT_TYPES_READ,
            PERMISSION_CONTENT_ENTRIES_READ,
            PERMISSION_MEDIA_ASSETS_READ,
        ),
    ),
)

PERMISSION_DEFINITIONS: tuple[PermissionDefinition, ...] = _PERMISSION_DEFINITIONS
ROLE_DEFINITIONS: tuple[RoleDefinition, ...] = _ROLE_DEFINITIONS
ROLE_DEFINITION_BY_KEY = {definition.key: definition for definition in ROLE_DEFINITIONS}


def get_permission_definitions() -> tuple[PermissionDefinition, ...]:
    """Return all built-in permission definitions.

    Args:
        None.

    Returns:
        tuple[PermissionDefinition, ...]: Ordered built-in permission definitions.

    Raises:
        None.
    """

    return PERMISSION_DEFINITIONS


def get_role_definitions() -> tuple[RoleDefinition, ...]:
    """Return all built-in role definitions.

    Args:
        None.

    Returns:
        tuple[RoleDefinition, ...]: Ordered built-in role definitions.

    Raises:
        None.
    """

    return ROLE_DEFINITIONS


def normalize_role_keys(role_keys: Iterable[str]) -> list[str]:
    """Normalize and validate requested role identifiers.

    Args:
        role_keys: Requested role identifiers.

    Returns:
        list[str]: Sorted unique normalized role identifiers.

    Raises:
        ValueError: If any requested role identifier is unknown.
    """

    normalized = sorted({value.strip().lower() for value in role_keys if value.strip()})
    invalid = [value for value in normalized if value not in ROLE_DEFINITION_BY_KEY]
    if invalid:
        invalid_roles = ', '.join(invalid)
        raise ValueError(f'Unknown role assignment requested: {invalid_roles}')
    return normalized


def has_role(user: Mapping[str, object], role_key: str) -> bool:
    """Return whether the supplied user has the requested role.

    Args:
        user: Authenticated user mapping.
        role_key: Stable role identifier.

    Returns:
        bool: True when the user has the role or is a root superuser.

    Raises:
        None.
    """

    if bool(user.get('is_superuser')):
        return True

    role_values = user.get('roles')
    if not isinstance(role_values, list):
        return False
    return role_key in role_values


def has_permission(user: Mapping[str, object], permission: str) -> bool:
    """Return whether the supplied user has the requested permission.

    Args:
        user: Authenticated user mapping.
        permission: Stable permission identifier.

    Returns:
        bool: True when the user has the permission or is a root superuser.

    Raises:
        None.
    """

    if bool(user.get('is_superuser')):
        return True

    permission_values = user.get('permissions')
    if not isinstance(permission_values, list):
        return False
    return permission in permission_values


def ensure_permission(user: Mapping[str, object], permission: str) -> None:
    """Raise a structured authorization failure when permission is missing.

    Args:
        user: Authenticated user mapping.
        permission: Stable permission identifier.

    Returns:
        None.

    Raises:
        AuthError: If the user lacks the requested permission.
    """

    if has_permission(user, permission):
        return

    raise AuthError(
        detail=f'Permission {permission} is required',
        code='AUTH_PERMISSION_DENIED',
        status_code=403,
    )

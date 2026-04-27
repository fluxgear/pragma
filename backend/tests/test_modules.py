# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Module subsystem integration tests for M10 backend scope.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import json
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pragma.app import create_app
from pragma.modules.manifest import ModuleManifest
from tests.helpers import build_database_dsn


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    """Bootstrap the first administrator account for module tests.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        AssertionError: If bootstrap fails unexpectedly.
    """

    response = client.post('/api/v1/install/bootstrap', json=bootstrap_payload)
    assert response.status_code == 201


def _auth_headers(client: TestClient, bootstrap_payload: dict[str, str]) -> dict[str, str]:
    """Log in the bootstrapped admin and return bearer-auth headers.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        dict[str, str]: Bearer authentication headers.

    Raises:
        AssertionError: If login fails unexpectedly.
    """

    _bootstrap_admin(client, bootstrap_payload)
    response = client.post(
        '/api/v1/auth/login',
        json={
            'identity': bootstrap_payload['email'],
            'password': bootstrap_payload['password'],
        },
    )
    assert response.status_code == 200
    access_token = response.json()['access_token']
    return {'Authorization': f'Bearer {access_token}'}


def _content_type_payload() -> dict[str, Any]:
    """Return a reusable content-type payload for module-event tests.

    Args:
        None.

    Returns:
        dict[str, Any]: Content-type creation payload.

    Raises:
        None.
    """

    return {
        'name': 'Blog Posts',
        'description': 'Structured blog content',
        'field_definitions': [
            {
                'name': 'title',
                'label': 'Title',
                'kind': 'text',
                'required': True,
                'min_length': 3,
                'max_length': 120,
            },
            {
                'name': 'body',
                'label': 'Body',
                'kind': 'rich_text',
                'required': True,
                'min_length': 1,
            },
            {
                'name': 'views',
                'label': 'Views',
                'kind': 'integer',
                'required': True,
                'minimum': 0,
            },
        ],
    }


def _create_content_type(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    """Create a reusable content type and return its response payload.

    Args:
        client: FastAPI test client.
        headers: Bearer authentication headers.

    Returns:
        dict[str, Any]: Parsed content-type response payload.

    Raises:
        AssertionError: If content-type creation fails unexpectedly.
    """

    response = client.post('/api/v1/content/types', headers=headers, json=_content_type_payload())
    assert response.status_code == 201
    return response.json()


def _write_module(
    module_root: Path,
    module_id: str,
    hooks_source: str,
    *,
    hooks: dict[str, str],
    order: int = 100,
) -> None:
    """Create a discoverable module directory with manifest and hooks file.

    Args:
        module_root: Module discovery root directory.
        module_id: Stable module identifier.
        hooks_source: Python source written to ``hooks.py``.
        hooks: Hook-event to callable-name mapping for ``module.json``.
        order: Deterministic module-order value for hook dispatch.

    Returns:
        None.

    Raises:
        None.
    """

    module_path = module_root / module_id
    module_path.mkdir(parents=True, exist_ok=True)
    manifest_payload = {
        'id': module_id,
        'name': module_id.replace('-', ' ').title(),
        'version': '1.0.0',
        'order': order,
        'entrypoint': 'hooks.py',
        'hooks': hooks,
    }
    (module_path / 'module.json').write_text(
        json.dumps(manifest_payload, indent=2),
        encoding='utf-8',
    )
    (module_path / 'hooks.py').write_text(
        textwrap.dedent(hooks_source).strip() + '\n',
        encoding='utf-8',
    )


def _enable_module(client: TestClient, headers: dict[str, str], module_id: str) -> None:
    """Enable a module via the module-state API and assert success.

    Args:
        client: FastAPI test client.
        headers: Bearer authentication headers.
        module_id: Target module identifier.

    Returns:
        None.

    Raises:
        AssertionError: If module-state update fails unexpectedly.
    """

    response = client.put(
        f'/api/v1/modules/{module_id}/state',
        headers=headers,
        json={'enabled': True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['enabled'] is True
    assert payload['loaded'] is True


def test_modules_migration_creates_state_table(migrated_database: dict[str, str]) -> None:
    """Verify M10 migration creates module-state table and index.

    Args:
        migrated_database: Environment values for the migrated test database.

    Returns:
        None.

    Raises:
        None.
    """

    database_dsn = build_database_dsn(
        migrated_database,
        migrated_database['PRAGMA_DATABASE_NAME'],
    )
    with psycopg.connect(database_dsn) as connection:
        row = connection.execute(
            """
            SELECT
                to_regclass('public.pragma_modules') AS modules_table,
                to_regclass('public.ix_pragma_modules_enabled') AS modules_enabled_index,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'pragma_modules'
                      AND column_name = 'module_id'
                ) AS has_module_id,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'pragma_modules'
                      AND column_name = 'enabled'
                ) AS has_enabled
            """
        ).fetchone()

    assert row[0] == 'pragma_modules'
    assert row[1] == 'ix_pragma_modules_enabled'
    assert row[2] is True
    assert row[3] is True


def test_module_manifest_rejects_unsupported_hook_events() -> None:
    """Verify manifest validation rejects unsupported hook event keys.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    with pytest.raises(ValidationError):
        ModuleManifest.model_validate(
            {
                'id': 'demo-module',
                'name': 'Demo Module',
                'version': '1.0.0',
                'entrypoint': 'hooks.py',
                'hooks': {'content.entry.invalid': 'on_invalid'},
            }
        )


def test_modules_api_lists_and_updates_persisted_state(
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify module lifecycle API lists and persists enable/disable state.

    Args:
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem path for module fixtures.

    Returns:
        None.

    Raises:
        None.
    """

    module_root = tmp_path / 'modules-api'
    module_root.mkdir(parents=True, exist_ok=True)
    _write_module(
        module_root,
        'sample-module',
        """
        def on_created(event):
            return None
        """,
        hooks={'content.entry.created': 'on_created'},
    )

    env_values = dict(migrated_database)
    env_values['PRAGMA_MODULE_ROOT'] = str(module_root)
    apply_runtime_env(env_values)

    with TestClient(create_app()) as client:
        headers = _auth_headers(client, bootstrap_payload)

        list_response = client.get('/api/v1/modules', headers=headers)
        assert list_response.status_code == 200
        assert list_response.json() == {
            'items': [
                {
                    'module_id': 'sample-module',
                    'name': 'Sample Module',
                    'version': '1.0.0',
                    'order': 100,
                    'enabled': False,
                    'loaded': False,
                    'hooks': [],
                    'error_code': None,
                }
            ],
            'total': 1,
        }

        enable_response = client.put(
            '/api/v1/modules/sample-module/state',
            headers=headers,
            json={'enabled': True},
        )
        assert enable_response.status_code == 200
        assert enable_response.json()['enabled'] is True
        assert enable_response.json()['loaded'] is True
        assert enable_response.json()['hooks'] == ['content.entry.created']

        disable_response = client.put(
            '/api/v1/modules/sample-module/state',
            headers=headers,
            json={'enabled': False},
        )
        assert disable_response.status_code == 200
        assert disable_response.json()['enabled'] is False
        assert disable_response.json()['loaded'] is False

    database_dsn = build_database_dsn(
        migrated_database,
        migrated_database['PRAGMA_DATABASE_NAME'],
    )
    with psycopg.connect(database_dsn) as connection:
        row = connection.execute(
            """
            SELECT enabled
            FROM pragma_modules
            WHERE module_id = %s
            """,
            ('sample-module',),
        ).fetchone()

    assert row[0] is False


def test_modules_api_requires_superuser(
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify module API access requires superuser authorization.

    Args:
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem path for module fixtures.

    Returns:
        None.

    Raises:
        None.
    """

    module_root = tmp_path / 'modules-auth'
    module_root.mkdir(parents=True, exist_ok=True)
    _write_module(
        module_root,
        'auth-module',
        """
        def on_created(event):
            return None
        """,
        hooks={'content.entry.created': 'on_created'},
    )

    env_values = dict(migrated_database)
    env_values['PRAGMA_MODULE_ROOT'] = str(module_root)
    apply_runtime_env(env_values)

    with TestClient(create_app()) as client:
        headers = _auth_headers(client, bootstrap_payload)
        database_dsn = build_database_dsn(
            migrated_database,
            migrated_database['PRAGMA_DATABASE_NAME'],
        )
        with psycopg.connect(database_dsn) as connection, connection.transaction():
            connection.execute(
                """
                UPDATE pragma_users
                SET is_superuser = FALSE
                WHERE email = %s
                """,
                (bootstrap_payload['email'],),
            )

        response = client.get('/api/v1/modules', headers=headers)

    assert response.status_code == 403
    assert response.json() == {
        'detail': 'Superuser privileges are required',
        'code': 'AUTH_SUPERUSER_REQUIRED',
    }


def test_modules_api_rejects_invalid_module_identifier(
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify module-state updates reject malformed module IDs cleanly.

    Args:
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem path for module fixtures.

    Returns:
        None.

    Raises:
        None.
    """

    module_root = tmp_path / 'modules-invalid-id'
    module_root.mkdir(parents=True, exist_ok=True)

    env_values = dict(migrated_database)
    env_values['PRAGMA_MODULE_ROOT'] = str(module_root)
    apply_runtime_env(env_values)

    with TestClient(create_app()) as client:
        headers = _auth_headers(client, bootstrap_payload)
        response = client.put(
            '/api/v1/modules/invalid.module/state',
            headers=headers,
            json={'enabled': True},
        )

    assert response.status_code == 400
    assert response.json() == {
        'detail': 'Module id must use lowercase letters, numbers, hyphens, or underscores',
        'code': 'MODULE_ID_INVALID',
    }


def test_content_entry_crud_dispatches_module_events(
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify create/update/delete dispatch stable module events.

    Args:
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem path for module fixtures.

    Returns:
        None.

    Raises:
        None.
    """

    log_path = tmp_path / 'module-events.log'
    module_root = tmp_path / 'modules-events'
    module_root.mkdir(parents=True, exist_ok=True)
    _write_module(
        module_root,
        'events-module',
        """
        import os
        from pathlib import Path


        def _append(value: str) -> None:
            with Path(os.environ['PRAGMA_MODULE_TEST_LOG']).open('a', encoding='utf-8') as handle:
                handle.write(f'{value}\\n')


        def on_created(event):
            _append('created')


        def on_updated(event):
            _append('updated')


        def on_deleted(event):
            _append('deleted')
        """,
        hooks={
            'content.entry.created': 'on_created',
            'content.entry.updated': 'on_updated',
            'content.entry.deleted': 'on_deleted',
        },
    )

    env_values = dict(migrated_database)
    env_values['PRAGMA_MODULE_ROOT'] = str(module_root)
    env_values['PRAGMA_MODULE_TEST_LOG'] = str(log_path)
    apply_runtime_env(env_values)

    with TestClient(create_app()) as client:
        headers = _auth_headers(client, bootstrap_payload)
        _enable_module(client, headers, 'events-module')
        content_type = _create_content_type(client, headers)

        create_response = client.post(
            '/api/v1/content/entries',
            headers=headers,
            json={
                'content_type_id': content_type['id'],
                'status': 'published',
                'payload': {
                    'title': 'Module Events',
                    'body': '<p>Created hook</p>',
                    'views': 1,
                },
            },
        )
        assert create_response.status_code == 201
        entry = create_response.json()

        update_response = client.put(
            f"/api/v1/content/entries/{entry['id']}",
            headers=headers,
            json={
                'status': 'published',
                'payload': {
                    'title': 'Module Events Updated',
                    'body': '<p>Updated hook</p>',
                    'views': 2,
                },
            },
        )
        assert update_response.status_code == 200

        delete_response = client.delete(
            f"/api/v1/content/entries/{entry['id']}",
            headers=headers,
        )
        assert delete_response.status_code == 204

    assert log_path.read_text(encoding='utf-8').strip().splitlines() == [
        'created',
        'updated',
        'deleted',
    ]


def test_content_entry_create_isolates_module_failures_and_dispatches_post_commit(
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify module failures are isolated and hooks run after transaction commit.

    Args:
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem path for module fixtures.

    Returns:
        None.

    Raises:
        None.
    """

    database_dsn = build_database_dsn(
        migrated_database,
        migrated_database['PRAGMA_DATABASE_NAME'],
    )
    log_path = tmp_path / 'module-dispatch.log'
    module_root = tmp_path / 'modules-dispatch'
    module_root.mkdir(parents=True, exist_ok=True)

    _write_module(
        module_root,
        'alpha-module',
        """
        import os
        from pathlib import Path


        def on_created(event):
            with Path(os.environ['PRAGMA_MODULE_TEST_LOG']).open('a', encoding='utf-8') as handle:
                handle.write('alpha\\n')
        """,
        hooks={'content.entry.created': 'on_created'},
        order=10,
    )
    _write_module(
        module_root,
        'beta-module',
        """
        import os
        from pathlib import Path


        def on_created(event):
            with Path(os.environ['PRAGMA_MODULE_TEST_LOG']).open('a', encoding='utf-8') as handle:
                handle.write('beta\\n')
            raise RuntimeError('beta hook failed')
        """,
        hooks={'content.entry.created': 'on_created'},
        order=20,
    )
    _write_module(
        module_root,
        'gamma-module',
        """
        import os

        import psycopg


        def on_created(event):
            entry_id = event['entry']['id']
            with psycopg.connect(os.environ['PRAGMA_MODULE_TEST_DSN']) as connection:
                row = connection.execute(
                    'SELECT COUNT(*) FROM pragma_content_entries WHERE id::text = %s',
                    (entry_id,),
                ).fetchone()
            if row[0] != 1:
                raise RuntimeError('entry transaction was not committed before dispatch')
            with open(os.environ['PRAGMA_MODULE_TEST_LOG'], 'a', encoding='utf-8') as handle:
                handle.write('gamma\\n')
        """,
        hooks={'content.entry.created': 'on_created'},
        order=30,
    )

    env_values = dict(migrated_database)
    env_values['PRAGMA_MODULE_ROOT'] = str(module_root)
    env_values['PRAGMA_MODULE_TEST_LOG'] = str(log_path)
    env_values['PRAGMA_MODULE_TEST_DSN'] = database_dsn
    apply_runtime_env(env_values)

    with TestClient(create_app()) as client:
        headers = _auth_headers(client, bootstrap_payload)
        for module_id in ('alpha-module', 'beta-module', 'gamma-module'):
            _enable_module(client, headers, module_id)

        content_type = _create_content_type(client, headers)
        create_response = client.post(
            '/api/v1/content/entries',
            headers=headers,
            json={
                'content_type_id': content_type['id'],
                'status': 'published',
                'payload': {
                    'title': 'Failure Isolation Entry',
                    'body': '<p>Module failure should not block CRUD.</p>',
                    'views': 7,
                },
            },
        )

        assert create_response.status_code == 201
        list_response = client.get('/api/v1/content/entries', headers=headers)
        assert list_response.status_code == 200
        assert list_response.json()['total'] == 1

    assert log_path.read_text(encoding='utf-8').strip().splitlines() == [
        'alpha',
        'beta',
        'gamma',
    ]

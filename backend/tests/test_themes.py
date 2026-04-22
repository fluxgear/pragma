# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Theme runtime integration and unit tests.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pragma.app import create_app
from pragma.config import get_settings
from pragma.errors import ThemeError
from pragma.themes import build_theme_runtime
from tests.helpers import build_runtime_env


def _build_theme_env(
    example_env_values: Mapping[str, str],
    theme_root: Path,
    *,
    database_name: str,
    active_theme_id: str = 'default',
    default_theme_id: str = 'default',
) -> dict[str, str]:
    """Build runtime environment values for theme tests.

    Args:
        example_env_values: Parsed example environment values.
        theme_root: Root directory for test themes.
        database_name: Database name for the current test context.
        active_theme_id: Configured active theme id.
        default_theme_id: Configured default theme id.

    Returns:
        dict[str, str]: Runtime environment values with theme overrides.

    Raises:
        None.
    """

    env_values = build_runtime_env(example_env_values, database_name)
    env_values['PRAGMA_THEME_ROOT'] = str(theme_root)
    env_values['PRAGMA_THEME_ACTIVE_ID'] = active_theme_id
    env_values['PRAGMA_THEME_DEFAULT_ID'] = default_theme_id
    return env_values


def _write_theme(
    theme_root: Path,
    directory_name: str,
    manifest: dict[str, object],
    *,
    templates: dict[str, str] | None = None,
    assets: dict[str, bytes] | None = None,
) -> Path:
    """Write a test theme to disk.

    Args:
        theme_root: Root directory for all test themes.
        directory_name: Directory name for the theme instance.
        manifest: Theme manifest payload.
        templates: Optional template files keyed by relative path.
        assets: Optional static files keyed by relative path.

    Returns:
        Path: Absolute path to the created theme directory.

    Raises:
        None.
    """

    theme_path = theme_root / directory_name
    theme_path.mkdir(parents=True, exist_ok=True)
    (theme_path / 'theme.json').write_text(json.dumps(manifest), encoding='utf-8')

    templates_dir = theme_path / str(manifest.get('templates_dir', 'templates'))
    for relative_path, content in (templates or {}).items():
        target = templates_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')

    static_dir = theme_path / str(manifest.get('static_dir', 'static'))
    for relative_path, content in (assets or {}).items():
        target = static_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    return theme_path


def test_theme_runtime_discovers_valid_themes_and_skips_invalid_duplicates(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify valid themes are discovered while invalid and duplicate manifests are skipped.

    Args:
        example_env_values: Parsed example environment values.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem root.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = tmp_path / 'themes'
    _write_theme(
        theme_root,
        '01-default',
        {'id': 'default', 'name': 'Default Theme', 'version': '1.0.0'},
    )
    _write_theme(
        theme_root,
        '02-default-duplicate',
        {'id': 'default', 'name': 'Duplicate Default', 'version': '2.0.0'},
    )
    _write_theme(
        theme_root,
        'custom',
        {'id': 'custom', 'name': 'Custom Theme', 'version': '1.0.0'},
    )
    broken_path = theme_root / 'broken'
    broken_path.mkdir(parents=True, exist_ok=True)
    (broken_path / 'theme.json').write_text('{"id": 42', encoding='utf-8')

    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_discovery',
        )
    )

    runtime = build_theme_runtime(get_settings())

    manifests = runtime.list_themes()
    assert {manifest.id for manifest in manifests} == {'custom', 'default'}
    assert runtime.resolve_default_theme().root_path.name == '01-default'


def test_theme_runtime_resolves_configured_active_theme(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify the configured active theme wins when it is available.

    Args:
        example_env_values: Parsed example environment values.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem root.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = tmp_path / 'themes'
    _write_theme(
        theme_root,
        'default',
        {'id': 'default', 'name': 'Default Theme', 'version': '1.0.0'},
    )
    _write_theme(
        theme_root,
        'custom',
        {'id': 'custom', 'name': 'Custom Theme', 'version': '1.0.0'},
    )

    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_active',
            active_theme_id='custom',
            default_theme_id='default',
        )
    )

    runtime = build_theme_runtime(get_settings())

    assert runtime.resolve_active_theme().manifest.id == 'custom'


def test_theme_runtime_prefers_active_template_when_present(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify active-theme templates override the default theme.

    Args:
        example_env_values: Parsed example environment values.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem root.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = tmp_path / 'themes'
    _write_theme(
        theme_root,
        'default',
        {'id': 'default', 'name': 'Default Theme', 'version': '1.0.0'},
        templates={'page.html': 'default {{ title }}'},
    )
    _write_theme(
        theme_root,
        'custom',
        {'id': 'custom', 'name': 'Custom Theme', 'version': '1.0.0'},
        templates={'page.html': 'custom {{ title }}'},
    )

    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_template_override',
            active_theme_id='custom',
            default_theme_id='default',
        )
    )

    runtime = build_theme_runtime(get_settings())

    assert runtime.resolve_template_path('page.html').theme_id == 'custom'
    assert runtime.render_template('page.html', {'title': 'Hello'}) == 'custom Hello'


def test_theme_runtime_falls_back_to_default_template_when_active_missing(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify missing active-theme templates fall back to the default theme.

    Args:
        example_env_values: Parsed example environment values.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem root.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = tmp_path / 'themes'
    _write_theme(
        theme_root,
        'default',
        {'id': 'default', 'name': 'Default Theme', 'version': '1.0.0'},
        templates={'page.html': 'default {{ title }}'},
    )
    _write_theme(
        theme_root,
        'custom',
        {'id': 'custom', 'name': 'Custom Theme', 'version': '1.0.0'},
    )

    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_template_missing',
            active_theme_id='custom',
            default_theme_id='default',
        )
    )

    runtime = build_theme_runtime(get_settings())

    assert runtime.resolve_template_path('page.html').theme_id == 'default'
    assert runtime.render_template('page.html', {'title': 'World'}) == 'default World'


def test_theme_runtime_falls_back_to_default_template_when_active_is_invalid(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify invalid active-theme templates fall back to the default theme.

    Args:
        example_env_values: Parsed example environment values.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem root.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = tmp_path / 'themes'
    _write_theme(
        theme_root,
        'default',
        {'id': 'default', 'name': 'Default Theme', 'version': '1.0.0'},
        templates={'page.html': 'default {{ title }}'},
    )
    _write_theme(
        theme_root,
        'custom',
        {'id': 'custom', 'name': 'Custom Theme', 'version': '1.0.0'},
        templates={'page.html': 'custom {{ title '},
    )

    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_template_invalid',
            active_theme_id='custom',
            default_theme_id='default',
        )
    )

    runtime = build_theme_runtime(get_settings())

    assert runtime.render_template('page.html', {'title': 'Fallback'}) == 'default Fallback'


def test_theme_runtime_reports_missing_templates_after_fallback_exhaustion(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify missing templates raise a stable theme-domain error.

    Args:
        example_env_values: Parsed example environment values.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem root.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = tmp_path / 'themes'
    _write_theme(
        theme_root,
        'default',
        {'id': 'default', 'name': 'Default Theme', 'version': '1.0.0'},
    )
    _write_theme(
        theme_root,
        'custom',
        {'id': 'custom', 'name': 'Custom Theme', 'version': '1.0.0'},
        templates={'page.html': 'custom {{ title '},
    )

    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_template_error',
            active_theme_id='custom',
            default_theme_id='default',
        )
    )

    runtime = build_theme_runtime(get_settings())

    with pytest.raises(ThemeError) as exc_info:
        runtime.render_template('missing.html')

    assert exc_info.value.code == 'THEME_TEMPLATE_NOT_FOUND'


def test_theme_runtime_resolves_assets_with_fallback_and_path_validation(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify asset lookups honor fallback order and reject traversal.

    Args:
        example_env_values: Parsed example environment values.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem root.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = tmp_path / 'themes'
    _write_theme(
        theme_root,
        'default',
        {'id': 'default', 'name': 'Default Theme', 'version': '1.0.0'},
        assets={'css/site.css': b'default'},
    )
    _write_theme(
        theme_root,
        'custom',
        {'id': 'custom', 'name': 'Custom Theme', 'version': '1.0.0'},
        assets={'images/logo.svg': b'custom-logo'},
    )

    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_assets',
            active_theme_id='custom',
            default_theme_id='default',
        )
    )

    runtime = build_theme_runtime(get_settings())

    assert runtime.resolve_asset_path('css/site.css').theme_id == 'default'
    assert runtime.resolve_asset_path('images/logo.svg').theme_id == 'custom'

    with pytest.raises(ThemeError) as exc_info:
        runtime.resolve_asset_path('../secrets.txt')

    assert exc_info.value.code == 'THEME_ASSET_PATH_INVALID'


def test_create_app_attaches_theme_runtime_without_checked_in_themes(
    runtime_database: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify app startup remains healthy when no repo theme tree exists yet.

    Args:
        runtime_database: Environment values for the isolated test database.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem root.

    Returns:
        None.

    Raises:
        None.
    """

    missing_theme_root = tmp_path / 'missing-themes'
    env_values = dict(runtime_database)
    env_values['PRAGMA_THEME_ROOT'] = str(missing_theme_root)
    env_values['PRAGMA_THEME_ACTIVE_ID'] = 'default'
    env_values['PRAGMA_THEME_DEFAULT_ID'] = 'default'
    apply_runtime_env(env_values)

    with TestClient(create_app()) as client:
        runtime = client.app.state.theme_runtime

    assert runtime.list_themes() == ()

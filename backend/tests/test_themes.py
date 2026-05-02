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
import tomllib
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


def _repo_theme_root() -> Path:
    """Return the checked-in repo theme root.

    Args:
        None.

    Returns:
        Path: Absolute path to the repository theme root.

    Raises:
        None.
    """

    return Path(__file__).resolve().parents[2] / 'themes'


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify active-theme templates override the default theme.

    Args:
        example_env_values: Parsed example environment values.
        apply_runtime_env: Helper that applies runtime environment values.
        tmp_path: Temporary filesystem root.
        monkeypatch: Pytest monkeypatch fixture.

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
    original_compile_template = runtime._compile_template
    compiled_paths: list[Path] = []

    def _record_compile_template(environment, name, resolved_path, globals=None, **kwargs):
        compiled_paths.append(resolved_path.filesystem_path)
        return original_compile_template(
            environment,
            name,
            resolved_path,
            globals,
            **kwargs,
        )

    monkeypatch.setattr(runtime, '_compile_template', _record_compile_template)

    assert runtime.resolve_template_path('page.html').theme_id == 'custom'
    assert runtime.render_template('page.html', {'title': 'Hello'}) == 'custom Hello'
    assert runtime.render_template('page.html', {'title': 'Again'}) == 'custom Again'
    assert compiled_paths == [theme_root / 'custom' / 'templates' / 'page.html']


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


def test_theme_runtime_falls_back_to_default_template_when_active_render_fails(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify render-time failures in the active theme fall back to default.

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
        templates={'page.html': '{{ 1 / 0 }}'},
    )

    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_render_failure',
            active_theme_id='custom',
            default_theme_id='default',
        )
    )

    runtime = build_theme_runtime(get_settings())

    assert runtime.render_template('page.html', {'title': 'Recovered'}) == 'default Recovered'


def test_theme_runtime_keeps_nested_default_fallback_theme_local(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify nested lookups stay in the default theme after fallback.

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
        templates={
            'base.html': 'DEFAULT BASE [{% block body %}{% endblock %}]',
            'fragment.html': 'DEFAULT FRAGMENT',
            'page.html': (
                '{% extends "base.html" %}'
                '{% block body %}{% include "fragment.html" %}{% endblock %}'
            ),
        },
    )
    _write_theme(
        theme_root,
        'custom',
        {'id': 'custom', 'name': 'Custom Theme', 'version': '1.0.0'},
        templates={
            'base.html': 'CUSTOM BASE [{% block body %}{% endblock %}]',
            'fragment.html': 'CUSTOM FRAGMENT',
        },
    )

    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_nested_fallback',
            active_theme_id='custom',
            default_theme_id='default',
        )
    )

    runtime = build_theme_runtime(get_settings())

    assert runtime.render_template('page.html') == 'DEFAULT BASE [DEFAULT FRAGMENT]'


def test_theme_runtime_normalizes_configured_theme_ids_before_resolution(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify configured theme identifiers are normalized before lookup.

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
            database_name='pragma_theme_id_normalization',
            active_theme_id=' Custom ',
            default_theme_id=' Default ',
        )
    )

    settings = get_settings()
    runtime = build_theme_runtime(settings)

    assert settings.theme_active_id == 'custom'
    assert settings.theme_default_id == 'default'
    assert runtime.resolve_active_theme().manifest.id == 'custom'
    assert runtime.resolve_default_theme().manifest.id == 'default'


def test_theme_runtime_reports_render_failure_after_fallback_exhaustion(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
    tmp_path: Path,
) -> None:
    """Verify a stable theme error is raised when all render attempts fail.

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
        templates={'page.html': '{{ 1 / 0 }}'},
    )
    _write_theme(
        theme_root,
        'custom',
        {'id': 'custom', 'name': 'Custom Theme', 'version': '1.0.0'},
        templates={'page.html': '{{ 1 / 0 }}'},
    )

    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_render_failure_exhausted',
            active_theme_id='custom',
            default_theme_id='default',
        )
    )

    runtime = build_theme_runtime(get_settings())

    with pytest.raises(ThemeError) as exc_info:
        runtime.render_template('page.html')

    assert exc_info.value.code == 'THEME_TEMPLATE_RENDER_FAILED'


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


def test_checked_in_default_theme_is_discoverable_and_selected(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
) -> None:
    """Verify the checked-in default theme is discoverable and selected.

    Args:
        example_env_values: Parsed example environment values.
        apply_runtime_env: Helper that applies runtime environment values.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = _repo_theme_root()
    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_checked_in_default',
        )
    )

    runtime = build_theme_runtime(get_settings())

    manifests = runtime.list_themes()
    assert any(manifest.id == 'default' for manifest in manifests)
    assert runtime.resolve_default_theme().root_path == theme_root / 'default'
    assert runtime.resolve_default_theme().manifest.name == 'Pragma Default Theme'


def test_checked_in_default_theme_covers_required_templates_and_assets(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
) -> None:
    """Verify the checked-in default theme exposes required templates, partials, and assets.

    Args:
        example_env_values: Parsed example environment values.
        apply_runtime_env: Helper that applies runtime environment values.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = _repo_theme_root()
    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_checked_in_assets',
        )
    )

    runtime = build_theme_runtime(get_settings())
    discovered_templates = set(runtime.environment.list_templates())

    assert {
        'home.html',
        'page.html',
        'post.html',
        'archive.html',
        'search.html',
        '404.html',
    }.issubset(discovered_templates)

    assert {
        'partials/header.html',
        'partials/footer.html',
        'partials/hero.html',
        'partials/services.html',
        'partials/testimonials.html',
        'partials/team.html',
        'partials/contact.html',
        'partials/blog-card.html',
    }.issubset(discovered_templates)

    for relative_path in (
        'css/main.css',
        'js/theme.js',
        'img/logo-mark.svg',
        'img/hero-grid.svg',
    ):
        resolved_asset = runtime.resolve_asset_path(relative_path)
        assert resolved_asset.theme_id == 'default'
        assert resolved_asset.filesystem_path == theme_root / 'default' / 'static' / relative_path
        assert resolved_asset.filesystem_path.is_file()


def test_checked_in_default_theme_templates_render_with_sparse_context(
    example_env_values: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
) -> None:
    """Verify sparse renders keep titles clean and fallback navigation actionable.

    Args:
        example_env_values: Parsed example environment values.
        apply_runtime_env: Helper that applies runtime environment values.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = _repo_theme_root()
    apply_runtime_env(
        _build_theme_env(
            example_env_values,
            theme_root,
            database_name='pragma_theme_checked_in_render',
        )
    )

    runtime = build_theme_runtime(get_settings())
    runtime = build_theme_runtime(get_settings())
    render_context = {'theme_static': '/themes/default/static'}

    rendered = {
        'home.html': runtime.render_template('home.html', render_context),
        'page.html': runtime.render_template('page.html', render_context),
        'post.html': runtime.render_template('post.html', render_context),
        'archive.html': runtime.render_template('archive.html', render_context),
        'search.html': runtime.render_template('search.html', render_context),
        '404.html': runtime.render_template('404.html', render_context),
    }

    expected_fragments = {
        'home.html': 'A public-facing foundation with the finish of a commercial product.',
        'page.html': 'A flexible page layout for polished long-form content.',
        'post.html': 'A refined article template with metadata, media, and related reading.',
        'archive.html': 'Browse the publication archive.',
        'search.html': 'Search is currently unavailable.',
        '404.html': 'The page you requested has gone missing.',
    }

    for template_name, fragment in expected_fragments.items():
        assert fragment in rendered[template_name]

    assert '<title>Pragma</title>' in rendered['page.html']
    assert 'Pragma · Pragma' not in rendered['page.html']
    assert '<meta name="robots" content="index,follow">' in rendered['page.html']
    assert '<meta property="og:type" content="website">' in rendered['page.html']
    assert '<meta name="twitter:card" content="summary">' in rendered['page.html']
    assert 'href="/#services"' in rendered['page.html']
    assert 'href="/#contact"' in rendered['page.html']
    assert 'href="/#search"' in rendered['page.html']
    assert 'href="#services"' not in rendered['page.html']
    assert 'href="#contact"' not in rendered['page.html']
    assert 'href="#search"' not in rendered['page.html']

    assert 'href="/#archive"' in rendered['post.html']
    assert 'href="#archive"' not in rendered['post.html']

    assert 'href="/#search"' in rendered['404.html']
    assert 'href="/#services"' in rendered['404.html']
    assert 'href="/#insights"' in rendered['404.html']
    assert 'href="/#contact"' in rendered['404.html']
    assert 'href="#search"' not in rendered['404.html']


def test_checked_in_default_theme_packaging_config_includes_repo_theme_tree() -> None:
    """Verify build configuration ships the checked-in theme tree to the installed runtime path.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    pyproject_path = Path(__file__).resolve().parents[1] / 'pyproject.toml'
    pyproject = tomllib.loads(pyproject_path.read_text(encoding='utf-8'))

    wheel_shared_data = pyproject['tool']['hatch']['build']['targets']['wheel']['shared-data']
    sdist_force_include = pyproject['tool']['hatch']['build']['targets']['sdist']['force-include']

    assert wheel_shared_data['themes'] == 'lib/themes'
    assert sdist_force_include['../themes'] == 'themes'


def test_checked_in_default_theme_shipped_sources_match_runtime_contracts() -> None:
    """Verify shipped source files encode the audited runtime contracts.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = _repo_theme_root() / 'default'
    archive_source = (
        theme_root / 'templates' / 'archive.html'
    ).read_text(encoding='utf-8')
    search_source = (
        theme_root / 'templates' / 'search.html'
    ).read_text(encoding='utf-8')
    page_source = (theme_root / 'templates' / 'page.html').read_text(encoding='utf-8')
    post_source = (theme_root / 'templates' / 'post.html').read_text(encoding='utf-8')
    css_source = (theme_root / 'static' / 'css' / 'main.css').read_text(encoding='utf-8')
    js_source = (theme_root / 'static' / 'js' / 'theme.js').read_text(encoding='utf-8')

    assert 'aria-disabled="true"' in archive_source
    assert 'aria-disabled="true"' in search_source
    assert "pagination.prev_url|default('#', true)" not in archive_source
    assert "pagination.next_url|default('#', true)" not in archive_source
    assert "pagination.prev_url|default('#', true)" not in search_source
    assert "pagination.next_url|default('#', true)" not in search_source
    assert '{# SECURITY: sanitized via nh3 #}' in page_source
    assert '{# SECURITY: sanitized via nh3 #}' in post_source
    assert '.meta-list' in css_source
    assert '.post-shell' in css_source
    assert 'resolveServerMode' in js_source
    assert 'window.matchMedia' in js_source


def test_create_app_attaches_checked_in_default_theme_runtime(
    runtime_database: dict[str, str],
    apply_runtime_env: Callable[[dict[str, str]], None],
) -> None:
    """Verify app startup attaches the checked-in default theme runtime.

    Args:
        runtime_database: Environment values for the isolated test database.
        apply_runtime_env: Helper that applies runtime environment values.

    Returns:
        None.

    Raises:
        None.
    """

    theme_root = _repo_theme_root()
    env_values = dict(runtime_database)
    env_values['PRAGMA_THEME_ROOT'] = str(theme_root)
    env_values['PRAGMA_THEME_ACTIVE_ID'] = 'default'
    env_values['PRAGMA_THEME_DEFAULT_ID'] = 'default'
    apply_runtime_env(env_values)

    with TestClient(create_app()) as client:
        runtime = client.app.state.theme_runtime

    assert runtime.resolve_default_theme().manifest.id == 'default'
    assert 'home.html' in runtime.environment.list_templates()

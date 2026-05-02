# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Public frontend integration tests.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import json
from importlib import import_module

import psycopg
import pytest
from fastapi.testclient import TestClient

from pragma.errors import StorageError, ThemeError
from tests.helpers import build_database_dsn

public_router_module = import_module('pragma.public.router')
public_service_module = import_module('pragma.public.service')


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    """Bootstrap the first administrator account for a test app.

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
    """Log in the bootstrapped admin and return auth headers.

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


def _content_type_payload(name: str, slug: str) -> dict[str, object]:
    """Return a reusable content-type payload for public tests.

    Args:
        name: Content-type name.
        slug: Content-type slug.

    Returns:
        dict[str, object]: Content-type payload.

    Raises:
        None.
    """

    return {
        'name': name,
        'slug': slug,
        'field_definitions': [
            {
                'name': 'title',
                'label': 'Title',
                'kind': 'text',
                'required': True,
                'min_length': 1,
                'max_length': 200,
            },
            {
                'name': 'subtitle',
                'label': 'Subtitle',
                'kind': 'text',
                'required': False,
                'max_length': 300,
            },
            {
                'name': 'summary',
                'label': 'Summary',
                'kind': 'text',
                'required': False,
                'max_length': 400,
            },
            {
                'name': 'author',
                'label': 'Author',
                'kind': 'text',
                'required': False,
                'max_length': 120,
            },
            {
                'name': 'category',
                'label': 'Category',
                'kind': 'text',
                'required': False,
                'max_length': 120,
            },
            {
                'name': 'featured_image_url',
                'label': 'Featured Image URL',
                'kind': 'text',
                'required': False,
                'max_length': 500,
            },
            {
                'name': 'featured_image_alt',
                'label': 'Featured Image Alt',
                'kind': 'text',
                'required': False,
                'max_length': 255,
            },
            {
                'name': 'body',
                'label': 'Body',
                'kind': 'rich_text',
                'required': True,
                'min_length': 1,
            },
        ],
    }


def _create_content_type(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    slug: str,
) -> dict[str, object]:
    """Create a content type and return the serialized response payload.

    Args:
        client: FastAPI test client.
        headers: Authenticated request headers.
        name: Content-type name.
        slug: Content-type slug.

    Returns:
        dict[str, object]: Serialized content-type response.

    Raises:
        AssertionError: If content-type creation fails unexpectedly.
    """

    response = client.post(
        '/api/v1/content/types',
        headers=headers,
        json=_content_type_payload(name=name, slug=slug),
    )
    assert response.status_code == 201
    return response.json()


def _create_entry(
    client: TestClient,
    headers: dict[str, str],
    content_type_id: str,
    *,
    title: str,
    body: str,
    status: str = 'published',
    subtitle: str | None = None,
    summary: str | None = None,
    author: str | None = None,
    category: str | None = None,
) -> dict[str, object]:
    """Create a content entry for public-route tests.

    Args:
        client: FastAPI test client.
        headers: Authenticated request headers.
        content_type_id: Owning content-type identifier.
        title: Entry title.
        body: Entry rich-text body.
        status: Requested content status.
        subtitle: Optional subtitle text.
        summary: Optional summary text.
        author: Optional author text.
        category: Optional category text.

    Returns:
        dict[str, object]: Serialized content-entry response.

    Raises:
        AssertionError: If entry creation fails unexpectedly.
    """

    payload: dict[str, str] = {'title': title, 'body': body}
    if subtitle is not None:
        payload['subtitle'] = subtitle
    if summary is not None:
        payload['summary'] = summary
    if author is not None:
        payload['author'] = author
    if category is not None:
        payload['category'] = category

    response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type_id,
            'status': status,
            'payload': payload,
        },
    )
    assert response.status_code == 201
    return response.json()


def _overwrite_entry_payload(
    migrated_database: dict[str, str],
    entry_id: str,
    payload: dict[str, object],
) -> None:
    """Overwrite stored entry payload to simulate imported legacy content.

    Args:
        migrated_database: Environment values for the migrated test database.
        entry_id: Stored content-entry identifier.
        payload: Replacement JSON payload.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL cannot update the stored payload.
    """

    dsn = build_database_dsn(migrated_database, migrated_database['PRAGMA_DATABASE_NAME'])
    with psycopg.connect(dsn) as connection, connection.transaction():
        connection.execute(
            "UPDATE pragma_content_entries SET payload = %s::jsonb WHERE id = %s",
            (json.dumps(payload), entry_id),
        )


def test_home_renders_theme_assets_and_seo_metadata(client: TestClient) -> None:
    """Verify the public homepage renders SEO metadata and theme assets.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.get('/')

    assert response.status_code == 200
    assert '/theme/static/css/main.css' in response.text
    assert '<meta name="robots" content="index,follow">' in response.text
    assert '<link rel="canonical" href=' in response.text
    assert 'href="/archive">Browse archive</a>' in response.text
    assert 'href="#archive"' not in response.text
    assert '<form class="contact-form"' not in response.text
    assert 'method="post"' not in response.text
    assert 'mailto:hello@example.com' in response.text
    assert 'Online enquiry submissions are not enabled for this site yet.' in response.text


def test_published_page_renders_body_title_and_canonical(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify published pages render rich body content and canonical metadata.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    page_type = _create_content_type(client, headers, name='Pages', slug='page')
    page_entry = _create_entry(
        client,
        headers,
        str(page_type['id']),
        title='About Pragma',
        subtitle='What we build',
        summary='About summary text',
        body='<p>Published page body</p>',
    )

    response = client.get(f"/pages/{page_entry['slug']}")

    assert response.status_code == 200
    assert 'About Pragma' in response.text
    assert 'Published page body' in response.text
    assert f'/pages/{page_entry["slug"]}' in response.text


def test_published_page_renders_rich_text_markup_without_escaping(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify declared rich_text body fields render trusted HTML markup.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    page_type = _create_content_type(client, headers, name='Pages', slug='page')
    page_entry = _create_entry(
        client,
        headers,
        str(page_type['id']),
        title='Trusted Rich Text Page',
        body='<p>Trusted <strong>rich text</strong> body</p>',
    )

    response = client.get(f"/pages/{page_entry['slug']}")

    assert response.status_code == 200
    assert '<strong>rich text</strong>' in response.text
    assert '&lt;strong&gt;rich text&lt;/strong&gt;' not in response.text


def test_updated_legacy_rich_text_is_sanitized_in_public_rendering(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    migrated_database: dict[str, str],
) -> None:
    """Verify unchanged legacy rich text is sanitized before public safe rendering.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.
        migrated_database: Environment values for the migrated test database.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    page_type = _create_content_type(client, headers, name='Pages', slug='page')
    page_entry = _create_entry(
        client,
        headers,
        str(page_type['id']),
        title='Legacy Rich Text Page',
        body='<p>Initial safe body</p>',
    )
    legacy_body = (
        '<p>Safe text before payload</p>'
        '<img src=x onerror=alert(1)>'
        '<script>alert(2)</script>'
    )
    _overwrite_entry_payload(
        migrated_database,
        str(page_entry['id']),
        {
            **page_entry['payload'],
            'body': legacy_body,
        },
    )

    update_response = client.put(
        f"/api/v1/content/entries/{page_entry['id']}",
        headers=headers,
        json={
            'status': 'published',
            'payload': {
                **page_entry['payload'],
                'title': 'Updated Legacy Rich Text Page',
                'body': legacy_body,
            },
        },
    )
    assert update_response.status_code == 200

    response = client.get(f"/pages/{page_entry['slug']}")

    assert response.status_code == 200
    assert 'Updated Legacy Rich Text Page' in response.text
    assert '<p>Safe text before payload</p>' in response.text
    assert '<img src=x' not in response.text
    assert 'onerror=alert(1)' not in response.text
    assert '<script>alert' not in response.text
    assert 'alert(2)' not in response.text
    assert '&lt;img' not in response.text
    assert '&lt;script' not in response.text


def test_page_with_plain_text_body_html_field_escapes_untrusted_markup(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify plain-text body_html fields are escaped in public rendering.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    content_type_response = client.post(
        '/api/v1/content/types',
        headers=headers,
        json={
            'name': 'Pages',
            'slug': 'page',
            'field_definitions': [
                {
                    'name': 'title',
                    'label': 'Title',
                    'kind': 'text',
                    'required': True,
                    'min_length': 1,
                    'max_length': 200,
                },
                {
                    'name': 'body_html',
                    'label': 'Body HTML',
                    'kind': 'text',
                    'required': True,
                    'min_length': 1,
                    'max_length': 2000,
                },
            ],
        },
    )
    assert content_type_response.status_code == 201
    content_type_id = str(content_type_response.json()['id'])

    entry_response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type_id,
            'status': 'published',
            'payload': {
                'title': 'Untrusted Body HTML',
                'body_html': '<script>alert(1)</script><p>Injected paragraph</p>',
            },
        },
    )
    assert entry_response.status_code == 201
    entry_slug = str(entry_response.json()['slug'])

    response = client.get(f'/pages/{entry_slug}')

    assert response.status_code == 200
    assert '<script>alert(1)</script>' not in response.text
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in response.text
    assert '&lt;p&gt;Injected paragraph&lt;/p&gt;' in response.text


def test_public_card_routes_skip_body_html_sanitization_for_card_entries(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify public card routes do not build full sanitized body views.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    post_type = _create_content_type(client, headers, name='Posts', slug='post')
    primary_post = _create_entry(
        client,
        headers,
        str(post_type['id']),
        title='Primary Card Route Post',
        summary='Primary card summary',
        body='<p>Primary full body</p>',
    )
    related_post = _create_entry(
        client,
        headers,
        str(post_type['id']),
        title='Related Card Route Post',
        summary='Related card summary',
        body='<p>Related card body</p>',
    )
    original_sanitizer = public_service_module._sanitize_public_body_html

    def _raise_for_related_card_body(value: str) -> str:
        if 'Related card body' in value:
            raise AssertionError('card route sanitized related body HTML')
        return original_sanitizer(value)

    monkeypatch.setattr(
        public_service_module,
        '_sanitize_public_body_html',
        _raise_for_related_card_body,
    )

    home_response = client.get('/')
    archive_response = client.get('/archive')
    post_response = client.get(f"/posts/{primary_post['slug']}")

    assert home_response.status_code == 200
    assert archive_response.status_code == 200
    assert post_response.status_code == 200
    assert 'Related Card Route Post' in home_response.text
    assert 'Related Card Route Post' in archive_response.text
    assert f'/posts/{related_post["slug"]}' in post_response.text


@pytest.mark.parametrize(
    ('content_type_slug', 'route_prefix'),
    [('page', 'pages'), ('post', 'posts')],
)
def test_draft_and_archived_slugs_render_themed_404_without_content_leaks(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    content_type_slug: str,
    route_prefix: str,
) -> None:
    """Verify draft and archived routes resolve to the same public 404 behavior.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.
        content_type_slug: Dynamic content-type slug under test.
        route_prefix: Public route prefix for the content type.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    content_type = _create_content_type(
        client,
        headers,
        name=content_type_slug.title(),
        slug=content_type_slug,
    )
    draft_entry = _create_entry(
        client,
        headers,
        str(content_type['id']),
        title=f'Secret {content_type_slug.title()} Draft',
        body='<p>Unpublished draft body</p>',
        status='draft',
    )
    archived_entry = _create_entry(
        client,
        headers,
        str(content_type['id']),
        title=f'Secret {content_type_slug.title()} Archive',
        body='<p>Archived body</p>',
        status='archived',
    )

    draft_response = client.get(f'/{route_prefix}/{draft_entry["slug"]}')
    archived_response = client.get(f'/{route_prefix}/{archived_entry["slug"]}')

    assert draft_response.status_code == 404
    assert archived_response.status_code == 404
    assert 'The page you requested has gone missing.' in draft_response.text
    assert 'The page you requested has gone missing.' in archived_response.text
    assert '<meta name="robots" content="noindex,follow">' in draft_response.text
    assert '<meta name="robots" content="noindex,follow">' in archived_response.text
    assert 'Secret' not in draft_response.text
    assert 'Secret' not in archived_response.text


def test_published_post_renders_metadata_and_related_posts_without_draft_leaks(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify post rendering includes metadata and published-only related cards.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    post_type = _create_content_type(client, headers, name='Posts', slug='post')
    primary_post = _create_entry(
        client,
        headers,
        str(post_type['id']),
        title='Primary Launch Post',
        summary='Primary summary',
        author='Author One',
        category='Engineering',
        body='<p>Primary published body</p>',
    )
    related_post = _create_entry(
        client,
        headers,
        str(post_type['id']),
        title='Related Published Post',
        summary='Related summary',
        author='Author Two',
        category='Engineering',
        body='<p>Related published body</p>',
    )
    _create_entry(
        client,
        headers,
        str(post_type['id']),
        title='Hidden Draft Post',
        summary='Draft summary',
        author='Author Hidden',
        category='Engineering',
        body='<p>Draft body</p>',
        status='draft',
    )

    response = client.get(f"/posts/{primary_post['slug']}")

    assert response.status_code == 200
    assert 'Primary Launch Post' in response.text
    assert 'Primary published body' in response.text
    assert 'Author One' in response.text
    assert 'Engineering' in response.text
    assert 'Related Published Post' in response.text
    assert f'/posts/{related_post["slug"]}' in response.text
    assert 'Hidden Draft Post' not in response.text


def test_archive_pagination_lists_only_published_entries_and_supports_empty_state(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify archive pagination and empty-state behavior for public routes.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    post_type = _create_content_type(client, headers, name='Posts', slug='post')
    first_title = 'Archive Post One'
    second_title = 'Archive Post Two'
    third_title = 'Archive Post Three'

    _create_entry(
        client,
        headers,
        str(post_type['id']),
        title=first_title,
        body='<p>First archive body</p>',
    )
    _create_entry(
        client,
        headers,
        str(post_type['id']),
        title=second_title,
        body='<p>Second archive body</p>',
    )
    _create_entry(
        client,
        headers,
        str(post_type['id']),
        title=third_title,
        body='<p>Third archive body</p>',
    )
    _create_entry(
        client,
        headers,
        str(post_type['id']),
        title='Archive Post Draft',
        body='<p>Draft archive body</p>',
        status='draft',
    )

    page_one = client.get('/archive', params={'page': 1, 'per_page': 2})
    page_two = client.get('/archive', params={'page': 2, 'per_page': 2})
    defaults_canonical = client.get(
        '/archive',
        params={'page': 1, 'per_page': 12, 'content_type': 'post'},
    )
    empty_state = client.get('/archive', params={'content_type': 'page'})

    assert page_one.status_code == 200
    assert page_two.status_code == 200
    assert defaults_canonical.status_code == 200
    combined_pages = page_one.text + page_two.text
    assert first_title in combined_pages
    assert second_title in combined_pages
    assert third_title in combined_pages
    assert 'Archive Post Draft' not in combined_pages
    disabled_previous = (
        '<span class="button button--secondary" aria-disabled="true">Previous</span>'
    )
    assert disabled_previous in page_one.text
    page_two_link = (
        '<a class="button button--secondary" href="/archive?page=2&amp;per_page=2">'
        'Next</a>'
    )
    assert page_two_link in page_one.text
    page_one_link = (
        '<a class="button button--secondary" href="/archive?page=1&amp;per_page=2">'
        'Previous</a>'
    )
    assert page_one_link in page_two.text
    disabled_next = (
        '<span class="button button--secondary" aria-disabled="true">Next</span>'
    )
    assert disabled_next in page_two.text
    assert 'pagination.prev_url|default' not in combined_pages
    assert 'pagination.next_url|default' not in combined_pages
    assert '<link rel="canonical" href="' in defaults_canonical.text
    assert '/archive?page=1' not in defaults_canonical.text
    assert '/archive?per_page=12' not in defaults_canonical.text
    assert '/archive?content_type=post' not in defaults_canonical.text
    assert '<link rel="canonical" href="' in page_one.text
    assert '/archive?per_page=2"' in page_one.text
    assert '/archive?page=1&amp;per_page=2"' not in page_one.text
    assert '/archive?page=2&amp;per_page=2"' in page_two.text

    assert empty_state.status_code == 200
    assert 'No archive entries are available.' in empty_state.text
    empty_state_message = (
        'Published entries will appear here automatically once they are available.'
    )
    assert empty_state_message in empty_state.text
    assert '/archive?content_type=page"' in empty_state.text
    assert '/archive?page=1' not in empty_state.text
    assert 'per_page=12' not in empty_state.text
    assert 'M8' not in empty_state.text
    assert 'M13' not in empty_state.text
    assert 'rollout' not in empty_state.text


def test_search_without_query_renders_no_query_state_without_invoking_search_service(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify blank search requests render no-query state and skip service calls.

    Args:
        client: FastAPI test client.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    def _raise_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError('search_public_entries should not run for blank queries')

    monkeypatch.setattr(public_router_module, 'search_public_entries', _raise_if_called)

    response = client.get('/search')

    assert response.status_code == 200
    assert 'Enter a search term to begin.' in response.text
    no_query_copy = (
        'Search published pages and posts, then use the archive when you want to '
        'browse everything available.'
    )
    assert no_query_copy in response.text
    assert 'M8' not in response.text
    assert 'M13' not in response.text
    assert 'rollout' not in response.text


def test_search_with_query_maps_results_to_public_urls_and_excludes_unpublished_entries(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify public search maps M8 results to page/post routes only.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    page_type = _create_content_type(client, headers, name='Pages', slug='page')
    post_type = _create_content_type(client, headers, name='Posts', slug='post')

    page_entry = _create_entry(
        client,
        headers,
        str(page_type['id']),
        title='Nebula Landing Page',
        body='<p>Nebula page content for discovery</p>',
    )
    post_entry = _create_entry(
        client,
        headers,
        str(post_type['id']),
        title='Nebula Operations Post',
        body='<p>Nebula post content for discovery</p>',
    )
    _create_entry(
        client,
        headers,
        str(post_type['id']),
        title='Nebula Draft Hidden',
        body='<p>Draft nebula content</p>',
        status='draft',
    )

    response = client.get('/search', params={'q': 'nebula'})

    assert response.status_code == 200
    assert 'Nebula Landing Page' in response.text
    assert 'Nebula Operations Post' in response.text
    assert f'/pages/{page_entry["slug"]}' in response.text
    assert f'/posts/{post_entry["slug"]}' in response.text
    assert 'Nebula Draft Hidden' not in response.text
    disabled_previous = (
        '<span class="button button--secondary" aria-disabled="true">Previous</span>'
    )
    disabled_next = (
        '<span class="button button--secondary" aria-disabled="true">Next</span>'
    )
    assert disabled_previous in response.text
    assert disabled_next in response.text
    assert 'pagination.prev_url|default' not in response.text
    assert 'pagination.next_url|default' not in response.text


def test_search_overlong_query_returns_visitor_safe_response(client: TestClient) -> None:
    """Verify overlong public search queries render a safe HTML response.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.get('/search', params={'q': 'x' * 201})
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    assert 'Search is temporarily unavailable.' in response.text
    assert 'Search queries must be 200 characters or fewer.' in response.text
    assert 'Search is not enabled yet.' not in response.text
    assert 'M8' not in response.text
    assert 'rollout' not in response.text


def test_search_no_results_state(client: TestClient) -> None:
    """Verify public search renders no-results state for unmatched queries.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.get('/search', params={'q': 'no-matching-phrase'})

    assert response.status_code == 200
    assert 'No results matched' in response.text


def test_theme_static_route_serves_assets_and_rejects_invalid_or_missing_paths(
    client: TestClient,
) -> None:
    """Verify public theme-static route serves assets and rejects invalid paths.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    css_response = client.get('/theme/static/css/main.css')
    js_response = client.get('/theme/static/js/theme.js')
    missing_response = client.get('/theme/static/css/not-real.css')
    traversal_response = client.get('/theme/static/%2e%2e/%2e%2e/.env')

    assert css_response.status_code == 200
    assert 'text/css' in css_response.headers['content-type']
    assert (
        css_response.headers['cache-control']
        == 'public, max-age=300, must-revalidate'
    )
    assert css_response.headers['etag']
    assert js_response.status_code == 200
    assert 'javascript' in js_response.headers['content-type']
    assert (
        js_response.headers['cache-control']
        == 'public, max-age=300, must-revalidate'
    )
    assert js_response.headers['etag']
    assert missing_response.status_code == 404
    assert traversal_response.status_code == 404


def test_themed_public_404_returns_http_404_with_noindex_metadata(client: TestClient) -> None:
    """Verify unmatched public paths render themed 404 with noindex SEO.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.get('/missing-public-path')

    assert response.status_code == 404
    assert 'The page you requested has gone missing.' in response.text
    assert '<meta name="robots" content="noindex,follow">' in response.text


def test_unknown_api_paths_preserve_structured_json_404(client: TestClient) -> None:
    """Verify unknown API routes still use structured JSON 404 responses.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.get('/api/v1/missing')

    assert response.status_code == 404
    assert response.headers['content-type'].startswith('application/json')
    payload = response.json()
    assert payload['detail'] == 'Not Found'
    assert payload['code'] == 'HTTP_404'


@pytest.mark.parametrize(
    ('route', 'patched_name'),
    [
        ('/', 'list_published_entries'),
        ('/pages/storage-outage', 'get_published_entry'),
        ('/posts/storage-outage', 'get_published_entry'),
        ('/archive', 'list_published_entries'),
    ],
)
def test_public_storage_outages_return_html_unavailable_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    patched_name: str,
) -> None:
    """Verify public visitor routes render HTML during storage outages.

    Args:
        client: FastAPI test client.
        monkeypatch: Pytest monkeypatch fixture.
        route: Public visitor route under test.
        patched_name: Public router storage helper to fail for the route.

    Returns:
        None.

    Raises:
        None.
    """

    def _raise_storage_error(*args: object, **kwargs: object) -> None:
        raise StorageError(
            detail='Internal storage failure detail should never leak',
            code='DATABASE_UNAVAILABLE',
        )

    monkeypatch.setattr(public_router_module, patched_name, _raise_storage_error)

    response = client.get(route)

    assert response.status_code == 503
    assert response.headers['content-type'].startswith('text/html')
    assert 'This page is temporarily unavailable.' in response.text
    assert 'Internal storage failure detail should never leak' not in response.text
    assert 'DATABASE_UNAVAILABLE' not in response.text


def test_public_storage_outage_fallback_preserves_html_when_theme_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify storage outage handling still returns fallback HTML if theming fails.

    Args:
        client: FastAPI test client.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    def _raise_storage_error(*args: object, **kwargs: object) -> None:
        raise StorageError(
            detail='Internal storage failure detail should never leak',
            code='DATABASE_UNAVAILABLE',
        )

    def _raise_theme_error(*args: object, **kwargs: object) -> str:
        raise ThemeError(
            detail='Internal template details should never leak',
            code='THEME_TEMPLATE_RENDER_FAILED',
        )

    monkeypatch.setattr(
        public_router_module,
        'list_published_entries',
        _raise_storage_error,
    )
    monkeypatch.setattr(client.app.state.theme_runtime, 'render_template', _raise_theme_error)

    response = client.get('/')

    assert response.status_code == 503
    assert response.headers['content-type'].startswith('text/html')
    assert 'temporarily unavailable' in response.text.lower()
    assert 'Internal storage failure detail should never leak' not in response.text
    assert 'Internal template details should never leak' not in response.text


def test_theme_render_failure_returns_visitor_safe_500_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify public render failures degrade to a visitor-safe HTML fallback.

    Args:
        client: FastAPI test client.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    def _raise_theme_error(*args: object, **kwargs: object) -> str:
        raise ThemeError(
            detail='Internal template details should never leak',
            code='THEME_TEMPLATE_RENDER_FAILED',
        )

    monkeypatch.setattr(client.app.state.theme_runtime, 'render_template', _raise_theme_error)

    response = client.get('/')

    assert response.status_code == 500
    assert 'temporarily unavailable' in response.text.lower()
    assert 'Internal template details should never leak' not in response.text

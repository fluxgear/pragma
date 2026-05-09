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
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout

from pragma.app import create_app
from pragma.errors import StorageError, ThemeError
from tests.helpers import build_database_dsn

public_router_module = import_module('pragma.public.router')
public_service_module = import_module('pragma.public.service')

_PNG_1X1 = (
    b'\x89PNG\r\n\x1a\n'
    b'\x00\x00\x00\rIHDR'
    b'\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde'
    b'\x00\x00\x00\x0bIDATx\x9cc```\x00\x00\x00\x04\x00\x01'
    b'\x0b\x0e-\xb4'
    b'\x00\x00\x00\x00IEND\xaeB`\x82'
)


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
    featured_image_url: str | None = None,
    featured_image_alt: str | None = None,
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
        featured_image_url: Optional featured image URL.
        featured_image_alt: Optional featured image alt text.

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
    if featured_image_url is not None:
        payload['featured_image_url'] = featured_image_url
    if featured_image_alt is not None:
        payload['featured_image_alt'] = featured_image_alt

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


def _valid_public_block_document() -> dict[str, object]:
    """Return a valid public-render block document covering baseline blocks."""

    return {
        'version': 1,
        'root': {
            'type': 'section',
            'settings': {'background': 'none', 'width': 'wide'},
            'children': [
                {
                    'type': 'container',
                    'children': [
                        {'type': 'heading', 'props': {'text': 'Block Hero', 'level': 2}},
                        {
                            'type': 'paragraph',
                            'props': {'html': '<p>Public <strong>block</strong> copy.</p>'},
                        },
                        {
                            'type': 'image',
                            'props': {
                                'media_id': '11111111-1111-1111-1111-111111111111',
                                'alt': 'Block image alt',
                                'caption': 'Block image caption',
                            },
                        },
                        {
                            'type': 'button',
                            'props': {'label': 'Start now', 'href': '/start'},
                            'settings': {'variant': 'primary'},
                        },
                        {
                            'type': 'list',
                            'props': {
                                'style': 'unordered',
                                'items': ['First item', 'Second item'],
                            },
                        },
                        {
                            'type': 'card',
                            'settings': {'variant': 'outlined'},
                            'children': [
                                {
                                    'type': 'heading',
                                    'props': {'text': 'Card title', 'level': 3},
                                },
                                {
                                    'type': 'paragraph',
                                    'props': {'html': '<p>Card body text.</p>'},
                                },
                            ],
                        },
                    ],
                }
            ],
        },
    }


def _create_block_page_type(
    client: TestClient,
    headers: dict[str, str],
) -> dict[str, object]:
    """Create a page content type with a block-document body field."""

    response = client.post(
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
                    'name': 'body',
                    'label': 'Body',
                    'kind': 'block_document',
                    'required': True,
                },
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_block_page_entry(
    client: TestClient,
    headers: dict[str, str],
    content_type_id: str,
    *,
    title: str,
    body: dict[str, object],
) -> dict[str, object]:
    """Create a published page entry with block-document body payload."""

    response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type_id,
            'status': 'published',
            'payload': {'title': title, 'body': body},
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
    assert 'Your public site is ready for published content.' in response.text
    assert 'class="metric-grid"' not in response.text
    assert 'Services are ready for configuration.' in response.text
    assert 'Testimonials can be enabled later.' in response.text
    assert 'Your team section is ready.' in response.text
    assert 'No posts are published yet.' in response.text
    published_posts_message = (
        'Published posts will appear here automatically once they are available.'
    )
    assert published_posts_message in response.text
    sample_homepage_content = (
        '32%',
        'faster publishing cycles',
        '4.8/5',
        'client satisfaction',
        '24/7',
        'operational confidence',
        'Positioning and narrative systems',
        'Content that reads like a product site',
        'Graceful empty and fallback states',
        'Elena Voss',
        'Marcus Trent',
        'Mara Stone',
        'Jonas Ivers',
        'Ari Patel',
    )
    for sample_text in sample_homepage_content:
        assert sample_text not in response.text

    assert 'Designing content systems that look enterprise-ready from day one' not in response.text
    assert 'Why resilient templates matter before public routing is complete' not in response.text
    assert 'Dark mode as a first-class public experience' not in response.text
    assert 'href="#"' not in response.text
    assert 'hello@example.com' not in response.text
    assert '+00 123 456 789' not in response.text
    assert 'mailto:hello@example.com' not in response.text


@pytest.mark.parametrize(
    (
        'published_reference_kind',
        'draft_reference_kind',
        'public_route_kind',
    ),
    [
        pytest.param(
            'api-absolute-content',
            'api-relative-content',
            'content',
            id='published-api-absolute-content-draft-api-relative-content',
        ),
        pytest.param(
            'api-relative-content',
            'api-absolute-content',
            'content',
            id='published-api-relative-content-draft-api-absolute-content',
        ),
        pytest.param(
            'public-relative-content',
            'api-relative-content',
            'content',
            id='published-public-relative-content-draft-api-relative-content',
        ),
        pytest.param(
            'public-absolute-content',
            'api-relative-content',
            'content',
            id='published-public-absolute-content-draft-api-relative-content',
        ),
        pytest.param(
            'api-absolute-content',
            'public-relative-content',
            'content',
            id='published-api-absolute-content-draft-public-relative-content',
        ),
        pytest.param(
            'api-absolute-content',
            'public-absolute-content',
            'content',
            id='published-api-absolute-content-draft-public-absolute-content',
        ),
        pytest.param(
            'api-relative-variant',
            'api-absolute-variant',
            'variant',
            id='published-api-relative-variant-draft-api-absolute-variant',
        ),
        pytest.param(
            'public-relative-variant',
            'api-absolute-variant',
            'variant',
            id='published-public-relative-variant-draft-api-absolute-variant',
        ),
        pytest.param(
            'public-absolute-variant',
            'api-absolute-variant',
            'variant',
            id='published-public-absolute-variant-draft-api-absolute-variant',
        ),
        pytest.param(
            'api-relative-variant',
            'public-relative-variant',
            'variant',
            id='published-api-relative-variant-draft-public-relative-variant',
        ),
        pytest.param(
            'api-relative-variant',
            'public-absolute-variant',
            'variant',
            id='published-api-relative-variant-draft-public-absolute-variant',
        ),
    ],
)
def test_public_media_route_serves_published_references_only(
    migrated_database: dict[str, str],
    apply_runtime_env,
    bootstrap_payload: dict[str, str],
    tmp_path: Path,
    published_reference_kind: str,
    draft_reference_kind: str,
    public_route_kind: str,
) -> None:
    """Verify public media authorization covers URL forms and variants."""

    _ = migrated_database
    media_root = tmp_path / 'public-media-root'
    apply_runtime_env(
        {
            'PRAGMA_MEDIA_ROOT': str(media_root),
            'PRAGMA_MEDIA_MAX_UPLOAD_BYTES': '1048576',
        }
    )

    def _reference_url(upload: dict[str, object], kind: str) -> str:
        """Return a content payload media reference for a URL form.

        Args:
            upload: Serialized media upload response.
            kind: URL form identifier.

        Returns:
            str: Media URL to store on the content entry payload.

        Raises:
            AssertionError: If the uploaded image lacks a thumbnail variant or
                the URL form is unknown.
        """

        media_id = str(upload['id'])
        content_url = str(upload['content_url'])
        variants = upload['variants']
        assert isinstance(variants, dict)
        thumbnail_url = str(variants['thumbnail'])

        if kind == 'api-absolute-content':
            return f'http://testserver{content_url}'
        if kind == 'api-relative-content':
            return content_url
        if kind == 'api-absolute-variant':
            return f'http://testserver{thumbnail_url}'
        if kind == 'api-relative-variant':
            return thumbnail_url
        if kind == 'public-relative-content':
            return f'/media/{media_id}/content'
        if kind == 'public-absolute-content':
            return f'http://testserver/media/{media_id}/content'
        if kind == 'public-relative-variant':
            return f'/media/{media_id}/variants/thumbnail'
        if kind == 'public-absolute-variant':
            return f'http://testserver/media/{media_id}/variants/thumbnail'

        raise AssertionError(f'Unknown public media URL form: {kind}')

    with TestClient(create_app()) as client:
        headers = _auth_headers(client, bootstrap_payload)
        published_upload_response = client.post(
            '/api/v1/media/assets?filename=published-hero.png',
            headers={**headers, 'Content-Type': 'image/png'},
            content=_PNG_1X1,
        )
        draft_upload_response = client.post(
            '/api/v1/media/assets?filename=draft-hero.png',
            headers={**headers, 'Content-Type': 'image/png'},
            content=_PNG_1X1,
        )
        assert published_upload_response.status_code == 201
        assert draft_upload_response.status_code == 201
        published_upload = published_upload_response.json()
        draft_upload = draft_upload_response.json()
        published_reference_url = _reference_url(
            published_upload,
            published_reference_kind,
        )
        draft_reference_url = _reference_url(draft_upload, draft_reference_kind)

        post_type = _create_content_type(client, headers, name='Posts', slug='post')
        published_entry = _create_entry(
            client,
            headers,
            str(post_type['id']),
            title='Public Media Post',
            body='<p>Published media body</p>',
            featured_image_url=published_reference_url,
            featured_image_alt='Published hero',
        )
        _create_entry(
            client,
            headers,
            str(post_type['id']),
            title='Draft Media Post',
            body='<p>Draft media body</p>',
            status='draft',
            featured_image_url=draft_reference_url,
            featured_image_alt='Draft hero',
        )

        page_response = client.get(f"/posts/{published_entry['slug']}")
        if public_route_kind == 'variant':
            public_media_url = f"/media/{published_upload['id']}/variants/thumbnail"
            draft_media_url = f"/media/{draft_upload['id']}/variants/thumbnail"
        else:
            public_media_url = f"/media/{published_upload['id']}/content"
            draft_media_url = f"/media/{draft_upload['id']}/content"
        published_media_response = client.get(public_media_url)
        draft_media_response = client.get(draft_media_url)

    assert page_response.status_code == 200
    assert public_media_url in page_response.text
    published_reference_is_absolute_public = published_reference_url.startswith(
        'http://testserver/media/'
    )
    expected_seo_image_url = (
        published_reference_url
        if published_reference_is_absolute_public
        else f'http://testserver{public_media_url}'
    )
    og_image_meta = '<meta property="og:image" content="'
    og_image_meta = f'{og_image_meta}{expected_seo_image_url}">'
    twitter_image_meta = '<meta name="twitter:image" content="'
    twitter_image_meta = f'{twitter_image_meta}{expected_seo_image_url}">'
    assert og_image_meta in page_response.text
    assert twitter_image_meta in page_response.text
    if (
        published_reference_url != public_media_url
        and not published_reference_is_absolute_public
    ):
        assert published_reference_url not in page_response.text
    assert published_media_response.status_code == 200
    if public_route_kind == 'variant':
        assert published_media_response.headers['content-type'].startswith('image/jpeg')
    else:
        assert published_media_response.content == _PNG_1X1
    assert draft_media_response.status_code == 404



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


def test_published_page_with_block_document_renders_baseline_blocks(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify public page rendering supports safe baseline block documents."""

    headers = _auth_headers(client, bootstrap_payload)
    page_type = _create_block_page_type(client, headers)
    page_entry = _create_block_page_entry(
        client,
        headers,
        str(page_type['id']),
        title='Block Landing Page',
        body=_valid_public_block_document(),
    )

    response = client.get(f"/pages/{page_entry['slug']}")

    assert response.status_code == 200
    assert 'Block Landing Page' in response.text
    assert '<h2 class="pragma-block pragma-block--heading">Block Hero</h2>' in response.text
    assert '<strong>block</strong>' in response.text
    assert 'src="/media/11111111-1111-1111-1111-111111111111/content"' in response.text
    assert 'alt="Block image alt"' in response.text
    button_html = (
        '<a class="pragma-block pragma-block--button pragma-block--button-primary" '
        'href="/start">Start now</a>'
    )
    assert button_html in response.text
    assert '<li>First item</li>' in response.text
    card_html = (
        '<article class="pragma-block pragma-block--card '
        'pragma-block--card-outlined">'
    )
    assert card_html in response.text
    assert 'Card body text.' in response.text


def test_malicious_stored_block_document_is_safely_rendered(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    migrated_database: dict[str, str],
) -> None:
    """Verify legacy/future stored block payloads cannot emit executable HTML."""

    headers = _auth_headers(client, bootstrap_payload)
    page_type = _create_block_page_type(client, headers)
    page_entry = _create_block_page_entry(
        client,
        headers,
        str(page_type['id']),
        title='Stored Malicious Blocks',
        body=_valid_public_block_document(),
    )
    malicious_body = {
        'version': 1,
        'root': {
            'type': 'section',
            'children': [
                {'type': 'heading', 'props': {'text': '<img src=x onerror=alert(1)>', 'level': 2}},
                {
                    'type': 'paragraph',
                    'props': {
                        'html': '<p onclick="alert(1)">Safe text</p><script>alert(2)</script>',
                    },
                },
                {
                    'type': 'button',
                    'props': {'label': 'Bad Link', 'href': 'javascript:alert(3)'},
                },
                {
                    'type': 'image',
                    'props': {'src': 'javascript:alert(4)', 'alt': 'Bad image'},
                },
            ],
        },
    }
    _overwrite_entry_payload(
        migrated_database,
        str(page_entry['id']),
        {'title': 'Stored Malicious Blocks', 'body': malicious_body},
    )

    response = client.get(f"/pages/{page_entry['slug']}")

    assert response.status_code == 200
    assert 'Stored Malicious Blocks' in response.text
    assert 'Safe text' in response.text
    assert 'alert(2)' not in response.text
    assert 'onclick=' not in response.text
    assert 'onerror=' not in response.text
    assert 'javascript:alert' not in response.text
    assert '<span class="pragma-block pragma-block--button">Bad Link</span>' in response.text
    assert '<img src="javascript:' not in response.text


def test_unknown_future_block_document_type_does_not_crash_public_rendering(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    migrated_database: dict[str, str],
) -> None:
    """Verify unknown stored block types are safely omitted on read."""

    headers = _auth_headers(client, bootstrap_payload)
    page_type = _create_block_page_type(client, headers)
    page_entry = _create_block_page_entry(
        client,
        headers,
        str(page_type['id']),
        title='Future Blocks Page',
        body=_valid_public_block_document(),
    )
    future_body = {
        'version': 1,
        'root': {
            'type': 'section',
            'children': [
                {'type': 'future-widget', 'props': {'html': '<script>alert(1)</script>'}},
                {'type': 'heading', 'props': {'text': 'Known block still renders', 'level': 2}},
            ],
        },
    }
    _overwrite_entry_payload(
        migrated_database,
        str(page_entry['id']),
        {'title': 'Future Blocks Page', 'body': future_body},
    )

    response = client.get(f"/pages/{page_entry['slug']}")

    assert response.status_code == 200
    assert 'Future Blocks Page' in response.text
    assert 'Known block still renders' in response.text
    assert 'future-widget' not in response.text
    assert 'alert(1)' not in response.text


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


def test_public_preview_renders_draft_only_with_valid_token_and_noindexes(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify signed preview tokens render drafts without public slug leaks."""

    from uuid import UUID

    from pragma.config import get_settings
    from pragma.content.service import create_content_entry_preview_token

    headers = _auth_headers(client, bootstrap_payload)
    page_type = _create_content_type(client, headers, name='Pages', slug='page')
    draft_entry = _create_entry(
        client,
        headers,
        str(page_type['id']),
        title='Preview Only Draft',
        body='<p>Private draft preview body</p>',
        status='draft',
    )

    public_response = client.get(f"/pages/{draft_entry['slug']}")
    token_response = client.post(
        f"/api/v1/content/entries/{draft_entry['id']}/preview",
        headers=headers,
    )
    assert token_response.status_code == 200
    preview_url = str(token_response.json()['preview_url'])
    preview_path = preview_url.removeprefix('http://testserver')

    preview_response = client.get(preview_path)
    invalid_response = client.get('/preview/content/not-a-token')
    tampered_response = client.get(f'{preview_path}x')
    expired_token, _ = create_content_entry_preview_token(
        get_settings(),
        entry_id=UUID(str(draft_entry['id'])),
        ttl_seconds=-60,
    )
    expired_response = client.get(f'/preview/content/{expired_token}')

    assert public_response.status_code == 404
    assert 'Preview Only Draft' not in public_response.text
    assert preview_response.status_code == 200
    assert 'Preview Only Draft' in preview_response.text
    assert 'Private draft preview body' in preview_response.text
    assert '<meta name="robots" content="noindex,nofollow">' in preview_response.text
    assert '<link rel="canonical" href="http://testserver/preview/content/' in preview_response.text
    assert f'http://testserver/pages/{draft_entry["slug"]}' not in preview_response.text
    for response in (invalid_response, tampered_response, expired_response):
        assert response.status_code == 404
        assert 'Preview Only Draft' not in response.text
        assert 'Private draft preview body' not in response.text


def test_published_page_renders_authorable_seo_metadata(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify B1 SEO metadata is rendered into published public pages."""

    headers = _auth_headers(client, bootstrap_payload)
    page_type = _create_content_type(client, headers, name='Pages', slug='page')
    entry_response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': page_type['id'],
            'status': 'published',
            'payload': {
                'title': 'Visible Page Title',
                'body': '<p>Published SEO page body</p>',
            },
            'seo_metadata': {
                'title': 'SEO Render Title',
                'description': 'SEO render description.',
                'canonical_url': '/custom-seo-canonical',
                'og_title': 'Social Render Title',
                'og_description': 'Social render description.',
                'og_image': 'https://cdn.example.test/social.png',
            },
        },
    )
    assert entry_response.status_code == 201
    entry = entry_response.json()

    response = client.get(f"/pages/{entry['slug']}")

    assert response.status_code == 200
    assert '<title>SEO Render Title ·' in response.text
    assert '<meta name="description" content="SEO render description.">' in response.text
    assert '<link rel="canonical" href="http://testserver/custom-seo-canonical">' in response.text
    assert '<meta property="og:title" content="Social Render Title">' in response.text
    assert '<meta property="og:description" content="Social render description.">' in response.text
    og_image_meta = (
        '<meta property="og:image" content="https://cdn.example.test/social.png">'
    )
    assert og_image_meta in response.text


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


@pytest.mark.parametrize(
    'search_exception',
    [
        PoolTimeout('test pool exhausted'),
        StorageError(
            detail='Internal search storage failure should never leak',
            code='DATABASE_UNAVAILABLE',
        ),
    ],
)
def test_search_storage_failures_return_visitor_safe_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    search_exception: Exception,
) -> None:
    """Verify public search degrades safely on storage-layer failures.

    Args:
        client: FastAPI test client.
        monkeypatch: Pytest monkeypatch fixture.
        search_exception: Storage/search exception raised by the search service.

    Returns:
        None.

    Raises:
        None.
    """

    def _raise_search_failure(*args: object, **kwargs: object) -> None:
        raise search_exception

    monkeypatch.setattr(
        public_router_module,
        'search_public_entries',
        _raise_search_failure,
    )

    response = client.get('/search', params={'q': 'nebula'})

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    assert 'Search is temporarily unavailable.' in response.text
    assert 'test pool exhausted' not in response.text
    assert 'Internal search storage failure should never leak' not in response.text
    assert 'DATABASE_UNAVAILABLE' not in response.text


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


def test_themes_api_requires_authentication(client: TestClient) -> None:
    """Verify theme administration API is protected."""

    response = client.get('/api/v1/themes')

    assert response.status_code == 401


def test_themes_api_requires_themes_manage_permission(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify authenticated users without themes.manage cannot administer themes.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    admin_headers = _auth_headers(client, bootstrap_payload)
    create_response = client.post(
        '/api/v1/users',
        headers=admin_headers,
        json={
            'email': 'theme-viewer@example.com',
            'username': 'themeviewer',
            'password': 'theme-viewer-password',
            'full_name': 'Theme Viewer',
            'is_active': True,
            'role_keys': ['viewer'],
            'force_password_change': False,
        },
    )
    assert create_response.status_code == 201
    login_response = client.post(
        '/api/v1/auth/login',
        json={
            'identity': 'theme-viewer@example.com',
            'password': 'theme-viewer-password',
        },
    )
    assert login_response.status_code == 200
    viewer_headers = {'Authorization': f"Bearer {login_response.json()['access_token']}"}

    list_response = client.get('/api/v1/themes', headers=viewer_headers)
    update_response = client.put(
        '/api/v1/themes/settings',
        headers=viewer_headers,
        json={'design_settings': {'primary_color': '#123abc'}},
    )
    reset_response = client.post(
        '/api/v1/themes/settings/reset',
        headers=viewer_headers,
    )

    for response in (list_response, update_response, reset_response):
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Permission themes.manage is required',
            'code': 'AUTH_PERMISSION_DENIED',
        }


def test_themes_api_updates_design_settings_and_public_context(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify safe design settings persist and flow into public template context."""

    headers = _auth_headers(client, bootstrap_payload)

    list_response = client.get('/api/v1/themes', headers=headers)
    update_response = client.put(
        '/api/v1/themes/settings',
        headers=headers,
        json={
            'design_settings': {
                'primary_color': '#123abc',
                'accent_color': '#654321',
                'typography_preset': 'serif',
                'spacing_scale': 'spacious',
                'radius_scale': 'large',
            },
        },
    )

    assert list_response.status_code == 200
    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload['design_settings']['primary_color'] == '#123abc'
    assert payload['design_settings']['typography_preset'] == 'serif'
    assert payload['current_theme_id'] == 'default'

    rendered_response = client.get('/')
    assert rendered_response.status_code == 200
    assert '<style id="pragma-design-settings">' in rendered_response.text
    assert '--site-primary: #123abc;' in rendered_response.text
    assert '--site-accent: #654321;' in rendered_response.text
    assert '--site-cta-start: #123abc;' in rendered_response.text
    assert '--site-cta-end: #654321;' in rendered_response.text
    assert '/theme/static/css/main.css' in rendered_response.text

    captured_context: dict[str, object] = {}

    def _capture_render(template_name: str, context: dict[str, object] | None = None) -> str:
        _ = template_name
        assert context is not None
        captured_context.update(context)
        return '<html><body>captured</body></html>'

    monkeypatch.setattr(client.app.state.theme_runtime, 'render_template', _capture_render)

    response = client.get('/')

    assert response.status_code == 200
    assert captured_context['design_settings']['primary_color'] == '#123abc'
    assert captured_context['site']['design']['typography_preset'] == 'serif'


def test_themes_api_rejects_invalid_activation_and_design_values(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify invalid theme ids and unsafe design values fail closed."""

    headers = _auth_headers(client, bootstrap_payload)

    missing_response = client.put(
        '/api/v1/themes/settings',
        headers=headers,
        json={'active_theme_id': 'missing-theme'},
    )
    unsafe_response = client.put(
        '/api/v1/themes/settings',
        headers=headers,
        json={'design_settings': {'primary_color': 'expression(alert(1))'}},
    )

    assert missing_response.status_code == 400
    assert missing_response.json()['code'] == 'THEME_ACTIVE_NOT_FOUND'
    assert unsafe_response.status_code == 422


def test_themes_api_reset_restores_environment_defaults(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify reset deletes persisted state and returns env/default behavior."""

    headers = _auth_headers(client, bootstrap_payload)
    update_response = client.put(
        '/api/v1/themes/settings',
        headers=headers,
        json={'design_settings': {'primary_color': '#123abc'}},
    )
    reset_response = client.post('/api/v1/themes/settings/reset', headers=headers)

    assert update_response.status_code == 200
    assert reset_response.status_code == 200
    payload = reset_response.json()
    assert payload['persisted_active_theme_id'] is None
    assert payload['active_theme_id'] == 'default'
    assert payload['design_settings']['primary_color'] == '#2563eb'

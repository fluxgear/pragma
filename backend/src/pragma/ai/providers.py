# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Provider-agnostic embedding request helpers.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from http import HTTPStatus
from urllib import error, request

from pragma.ai.models import AIProvider
from pragma.errors import SearchError


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    """Runtime provider configuration required for embedding requests.

    Args:
        provider: Provider identifier.
        base_url: Provider API base URL.
        api_key: Bearer API key.
        embedding_model: Provider model identifier.
        request_timeout_seconds: Network timeout for provider calls.

    Returns:
        None.

    Raises:
        None.
    """

    provider: AIProvider
    base_url: str
    api_key: str
    embedding_model: str
    request_timeout_seconds: int


def _embedding_url(base_url: str) -> str:
    """Return the canonical embeddings endpoint for a provider base URL.

    Args:
        base_url: Configured provider base URL.

    Returns:
        str: Fully-qualified embeddings endpoint URL.

    Raises:
        None.
    """

    return f"{base_url.rstrip('/')}/embeddings"


def _embedding_payload(
    config: EmbeddingProviderConfig,
    text: str,
    *,
    input_type: str,
) -> dict[str, object]:
    """Build provider-specific JSON payload for embedding generation.

    Args:
        config: Provider runtime configuration.
        text: Source text to embed.
        input_type: Provider-side input intent (query or document).

    Returns:
        dict[str, object]: JSON-serializable request payload.

    Raises:
        None.
    """

    if config.provider is AIProvider.VOYAGE:
        return {
            'input': [text],
            'model': config.embedding_model,
            'input_type': input_type,
        }
    return {
        'input': text,
        'model': config.embedding_model,
        'encoding_format': 'float',
    }


def _extract_embedding(response_payload: dict[str, object]) -> list[float]:
    """Extract the first embedding vector from a provider response payload.

    Args:
        response_payload: Parsed JSON payload from the provider.

    Returns:
        list[float]: Embedding vector values.

    Raises:
        ValueError: If the response cannot be interpreted as an embedding payload.
    """

    data = response_payload.get('data')
    if isinstance(data, list) and data:
        first_item = data[0]
        if isinstance(first_item, dict) and isinstance(first_item.get('embedding'), list):
            values = first_item['embedding']
            return [float(item) for item in values]

    embeddings = response_payload.get('embeddings')
    if isinstance(embeddings, list) and embeddings:
        first_embedding = embeddings[0]
        if isinstance(first_embedding, list):
            return [float(item) for item in first_embedding]

    raise ValueError('Provider response is missing embedding data')


def request_embedding(
    config: EmbeddingProviderConfig,
    text: str,
    *,
    input_type: str,
) -> list[float]:
    """Generate an embedding vector via the configured provider.

    Args:
        config: Provider runtime configuration.
        text: Source text to embed.
        input_type: Provider-side input intent (query or document).

    Returns:
        list[float]: Embedding vector values.

    Raises:
        SearchError: If the provider request fails or returns invalid data.
    """

    payload = _embedding_payload(config, text, input_type=input_type)
    body = json.dumps(payload).encode('utf-8')
    http_request = request.Request(
        _embedding_url(config.base_url),
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.api_key}',
        },
        method='POST',
    )

    try:
        with request.urlopen(
            http_request,
            timeout=config.request_timeout_seconds,
        ) as response:
            response_body = response.read()
    except error.HTTPError as exc:
        raise SearchError(
            detail='Embedding provider rejected the request',
            code='SEARCH_EMBEDDING_PROVIDER_REJECTED',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        ) from exc
    except error.URLError as exc:
        raise SearchError(
            detail='Embedding provider is unavailable',
            code='SEARCH_EMBEDDING_PROVIDER_UNAVAILABLE',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        ) from exc
    except TimeoutError as exc:
        raise SearchError(
            detail='Embedding provider timed out',
            code='SEARCH_EMBEDDING_PROVIDER_UNAVAILABLE',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        ) from exc

    try:
        decoded = response_body.decode('utf-8')
        response_payload = json.loads(decoded)
        embedding = _extract_embedding(response_payload)
    except UnicodeDecodeError as exc:
        raise SearchError(
            detail='Embedding provider returned unreadable data',
            code='SEARCH_EMBEDDING_PROVIDER_INVALID',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        ) from exc
    except json.JSONDecodeError as exc:
        raise SearchError(
            detail='Embedding provider returned invalid JSON',
            code='SEARCH_EMBEDDING_PROVIDER_INVALID',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        ) from exc
    except ValueError as exc:
        raise SearchError(
            detail='Embedding provider response was missing vector data',
            code='SEARCH_EMBEDDING_PROVIDER_INVALID',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        ) from exc

    if not embedding or any(not math.isfinite(value) for value in embedding):
        raise SearchError(
            detail='Embedding provider response contained invalid vector values',
            code='SEARCH_EMBEDDING_PROVIDER_INVALID',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )
    return embedding

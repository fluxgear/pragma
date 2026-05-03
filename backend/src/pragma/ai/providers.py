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

import http.client
import ipaddress
import json
import math
import socket
import ssl
from dataclasses import dataclass
from http import HTTPStatus
from urllib import error, parse, request

from pragma.ai.models import AIProvider
from pragma.errors import SearchError

_MAX_EMBEDDING_RESPONSE_BYTES = 1024 * 1024
_EMBEDDING_RESPONSE_READ_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    """Runtime provider configuration required for embedding requests.

    Args:
        provider: Provider identifier.
        base_url: Provider API base URL.
        api_key: Bearer API key.
        embedding_model: Provider model identifier.
        embedding_dimensions: Expected embedding vector dimensions.
        request_timeout_seconds: Network timeout for provider calls.
        allow_private_base_urls: Whether runtime requests may target private or
            local provider hosts.

    Returns:
        None.

    Raises:
        None.
    """

    provider: AIProvider
    base_url: str
    api_key: str
    embedding_model: str
    embedding_dimensions: int
    request_timeout_seconds: int
    allow_private_base_urls: bool = False


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


def _raise_unsafe_provider_target() -> None:
    """Raise the standard unsafe-runtime-target provider error.

    Args:
        None.

    Returns:
        None.

    Raises:
        SearchError: Always, because private/local provider targets are unsafe.
    """

    raise SearchError(
        detail=(
            'Embedding provider URL must not resolve to private or local network '
            'targets unless explicitly allowed'
        ),
        code='SEARCH_EMBEDDING_PROVIDER_INVALID',
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
    )


def _is_private_or_local_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """Return whether an IP address targets a non-public network.

    Args:
        address: Parsed IP address returned from runtime DNS resolution.

    Returns:
        bool: True when the address is private, local, reserved, or otherwise
            unsuitable for outbound provider traffic.

    Raises:
        None.
    """

    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _validate_runtime_provider_target(
    url: str,
    *,
    allow_private_base_urls: bool,
) -> tuple[parse.SplitResult, tuple[tuple[int, tuple[object, ...]], ...]]:
    """Validate the concrete outbound provider target at request time.

    Args:
        url: Fully qualified provider request URL.
        allow_private_base_urls: Whether operator configuration explicitly
            permits private, local, or non-HTTPS provider targets.

    Returns:
        tuple[parse.SplitResult, tuple[tuple[int, tuple[object, ...]], ...]]:
            Parsed request URL and concrete resolved socket targets.

    Raises:
        SearchError: If the outbound target is malformed, unavailable, or
            resolves to an unsafe private/local address.
    """

    parsed = parse.urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise SearchError(
            detail='Embedding provider URL is invalid',
            code='SEARCH_EMBEDDING_PROVIDER_INVALID',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )
    if parsed.scheme != 'https' and not allow_private_base_urls:
        raise SearchError(
            detail=(
                'Embedding provider URL must use HTTPS unless private AI URLs are '
                'explicitly allowed'
            ),
            code='SEARCH_EMBEDDING_PROVIDER_INVALID',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    hostname = parsed.hostname.strip().rstrip('.').lower()
    if (hostname == 'localhost' or hostname.endswith('.localhost')) and not allow_private_base_urls:
        _raise_unsafe_provider_target()

    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    try:
        resolved_targets = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise SearchError(
            detail='Embedding provider is unavailable',
            code='SEARCH_EMBEDDING_PROVIDER_UNAVAILABLE',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        ) from exc

    if not resolved_targets:
        raise SearchError(
            detail='Embedding provider is unavailable',
            code='SEARCH_EMBEDDING_PROVIDER_UNAVAILABLE',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    concrete_targets: list[tuple[int, tuple[object, ...]]] = []
    for family, _type, _proto, _canonname, sockaddr in resolved_targets:
        resolved_address = ipaddress.ip_address(str(sockaddr[0]))
        if _is_private_or_local_address(resolved_address) and not allow_private_base_urls:
            _raise_unsafe_provider_target()
        concrete_targets.append((family, tuple(sockaddr)))

    return parsed, tuple(concrete_targets)


class _RejectRedirectHandler(request.HTTPRedirectHandler):
    """Disallow redirect hops for outbound embedding requests.

    Args:
        None.

    Returns:
        None.

    Raises:
        SearchError: Always, because redirect-based provider pivots are unsafe.
    """

    def redirect_request(
        self,
        req: request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> request.Request | None:
        """Reject redirect responses for embedding-provider traffic.

        Args:
            req: Original outbound request.
            fp: Response file object supplied by urllib.
            code: HTTP redirect status code.
            msg: HTTP redirect reason phrase.
            headers: HTTP response headers.
            newurl: Redirect destination URL.

        Returns:
            request.Request | None: Never returns.

        Raises:
            SearchError: Always, because embedding provider redirects are disallowed.
        """

        del req, fp, code, msg, headers, newurl
        raise SearchError(
            detail='Embedding provider redirects are not allowed',
            code='SEARCH_EMBEDDING_PROVIDER_INVALID',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )


class _DirectHTTPConnection(http.client.HTTPConnection):
    """HTTP connection bound to a prevalidated socket target.

    Args:
        host: Original provider hostname for request metadata.
        family: Address family to connect with.
        sockaddr: Concrete resolved socket target tuple.
        timeout: Network timeout in seconds.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        host: str,
        *,
        family: int,
        sockaddr: tuple[object, ...],
        timeout: int,
    ) -> None:
        super().__init__(host=host, timeout=timeout)
        self._family = family
        self._sockaddr = sockaddr

    def connect(self) -> None:
        """Connect using the prevalidated socket address.

        Args:
            None.

        Returns:
            None.

        Raises:
            OSError: If the socket cannot connect.
        """

        self.sock = socket.socket(self._family, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._sockaddr)


class _DirectHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection bound to a prevalidated socket target.

    Args:
        host: Original provider hostname for SNI and certificate validation.
        family: Address family to connect with.
        sockaddr: Concrete resolved socket target tuple.
        timeout: Network timeout in seconds.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        host: str,
        *,
        family: int,
        sockaddr: tuple[object, ...],
        timeout: int,
    ) -> None:
        super().__init__(host=host, timeout=timeout, context=ssl.create_default_context())
        self._family = family
        self._sockaddr = sockaddr

    def connect(self) -> None:
        """Connect using the prevalidated socket address with TLS.

        Args:
            None.

        Returns:
            None.

        Raises:
            OSError: If the socket cannot connect or TLS setup fails.
        """

        raw_socket = socket.socket(self._family, socket.SOCK_STREAM)
        raw_socket.settimeout(self.timeout)
        raw_socket.connect(self._sockaddr)
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


class _BoundResponse:
    """Context-managed HTTP response that closes its backing connection.

    Args:
        connection: Live direct HTTP connection.
        response: HTTP response object bound to the connection.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self, connection: http.client.HTTPConnection, response: object) -> None:
        self._connection = connection
        self._response = response

    def __enter__(self) -> object:
        return self._response

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self._connection.close()


def _open_embedding_request(
    http_request: request.Request,
    *,
    timeout: int,
    parsed_url: parse.SplitResult,
    resolved_targets: tuple[tuple[int, tuple[object, ...]], ...],
) -> object:
    """Open an embedding request bound to prevalidated socket targets.

    Args:
        http_request: Prepared outbound HTTP request.
        timeout: Network timeout in seconds.
        parsed_url: Parsed request URL.
        resolved_targets: Prevalidated concrete socket targets for the request host.

    Returns:
        object: Context-managed file-like HTTP response object.

    Raises:
        error.URLError: If all validated targets fail to connect.
        SearchError: If a provider redirect is attempted.
    """

    path = parsed_url.path or '/'
    if parsed_url.query:
        path = f'{path}?{parsed_url.query}'

    last_error: OSError | None = None
    for family, sockaddr in resolved_targets:
        if parsed_url.scheme == 'https':
            connection = _DirectHTTPSConnection(
                parsed_url.hostname or '',
                family=family,
                sockaddr=sockaddr,
                timeout=timeout,
            )
        else:
            connection = _DirectHTTPConnection(
                parsed_url.hostname or '',
                family=family,
                sockaddr=sockaddr,
                timeout=timeout,
            )
        try:
            connection.request(
                http_request.get_method(),
                path,
                body=http_request.data,
                headers=dict(http_request.header_items()),
            )
            response = connection.getresponse()
            if 300 <= response.status < 400:
                response.read()
                connection.close()
                raise SearchError(
                    detail='Embedding provider redirects are not allowed',
                    code='SEARCH_EMBEDDING_PROVIDER_INVALID',
                    status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                )
            return _BoundResponse(connection, response)
        except SearchError:
            raise
        except OSError as exc:
            connection.close()
            last_error = exc

    raise error.URLError(last_error or OSError('connection failed'))


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
        if isinstance(first_embedding, dict) and isinstance(first_embedding.get('embedding'), list):
            values = first_embedding['embedding']
            return [float(item) for item in values]

    raise ValueError('Provider response is missing embedding data')


def _raise_embedding_response_too_large() -> None:
    """Raise the standard oversized provider-response error."""

    raise SearchError(
        detail='Embedding provider response exceeded the configured read limit',
        code='SEARCH_EMBEDDING_PROVIDER_INVALID',
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
    )


def _read_limited_response_body(response: object) -> bytes:
    """Read a provider response body within a fixed memory bound."""

    content_length = None
    getheader = getattr(response, 'getheader', None)
    if callable(getheader):
        content_length = getheader('Content-Length')
    if content_length is None:
        headers = getattr(response, 'headers', None)
        if headers is not None:
            content_length = headers.get('Content-Length')

    if (
        isinstance(content_length, str)
        and content_length.strip().isdecimal()
        and int(content_length.strip()) > _MAX_EMBEDDING_RESPONSE_BYTES
    ):
        _raise_embedding_response_too_large()

    chunks: list[bytes] = []
    received_size = 0
    while True:
        read_size = min(
            _EMBEDDING_RESPONSE_READ_CHUNK_BYTES,
            _MAX_EMBEDDING_RESPONSE_BYTES + 1 - received_size,
        )
        chunk = response.read(read_size)  # type: ignore[attr-defined]
        if not chunk:
            break
        received_size += len(chunk)
        if received_size > _MAX_EMBEDDING_RESPONSE_BYTES:
            _raise_embedding_response_too_large()
        chunks.append(chunk)

    return b''.join(chunks)


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
        list[float]: Provider embedding vector.

    Raises:
        SearchError: If the provider target is unsafe, unavailable, rejects the
            request, or returns invalid embedding data.
    """

    payload = _embedding_payload(config, text, input_type=input_type)
    body = json.dumps(payload).encode('utf-8')
    endpoint_url = _embedding_url(config.base_url)

    try:
        parsed_url, resolved_targets = _validate_runtime_provider_target(
            endpoint_url,
            allow_private_base_urls=config.allow_private_base_urls,
        )
        http_request = request.Request(
            endpoint_url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config.api_key}',
            },
            method='POST',
        )
        with _open_embedding_request(
            http_request,
            timeout=config.request_timeout_seconds,
            parsed_url=parsed_url,
            resolved_targets=resolved_targets,
        ) as response:
            response_body = _read_limited_response_body(response)
    except ValueError as exc:
        raise SearchError(
            detail='Embedding provider URL is invalid',
            code='SEARCH_EMBEDDING_PROVIDER_INVALID',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        ) from exc
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
    if (
        config.embedding_dimensions is not None
        and len(embedding) != config.embedding_dimensions
    ):
        raise SearchError(
            detail=(
                'Embedding provider returned vector dimensions that do not match '
                'the configured AI settings'
            ),
            code='SEARCH_EMBEDDING_DIMENSION_MISMATCH',
            status_code=HTTPStatus.BAD_GATEWAY,
        )
    return embedding

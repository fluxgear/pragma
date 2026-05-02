# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Storage backends for the Pragma media library.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from pragma.config import Settings
from pragma.errors import ConfigError, StorageError

_MULTI_HYPHEN_PATTERN = re.compile(r'-{2,}')
_STREAM_COPY_CHUNK_SIZE = 1024 * 1024
_MIME_EXTENSION_MAP = {
    'application/pdf': '.pdf',
    'audio/mpeg': '.mp3',
    'audio/ogg': '.ogg',
    'audio/wav': '.wav',
    'image/gif': '.gif',
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'video/mp4': '.mp4',
    'video/webm': '.webm',
}


@dataclass(frozen=True, slots=True)
class StoredMedia:
    """Resolved storage metadata for a saved media object.

    Args:
        storage_key: Stable relative storage identifier.
        filesystem_path: Absolute local filesystem path.

    Returns:
        None.

    Raises:
        None.
    """

    storage_key: str
    filesystem_path: Path


class StorageBackend(ABC):
    """Abstract storage backend for media objects."""

    def store(
        self,
        media_id: UUID,
        original_filename: str,
        data: bytes,
        mime_type: str,
        created_at: datetime,
    ) -> StoredMedia:
        """Persist raw media bytes."""

        return self.store_from_stream(
            media_id=media_id,
            original_filename=original_filename,
            source=BytesIO(data),
            mime_type=mime_type,
            created_at=created_at,
        )

    @abstractmethod
    def store_from_stream(
        self,
        media_id: UUID,
        original_filename: str,
        source: BinaryIO,
        mime_type: str,
        created_at: datetime,
    ) -> StoredMedia:
        """Persist media bytes from a readable binary stream."""

    @abstractmethod
    def store_variant_from_stream(
        self,
        media_id: UUID,
        variant_name: str,
        source: BinaryIO,
        mime_type: str,
        created_at: datetime,
    ) -> StoredMedia:
        """Persist derivative media bytes from a readable binary stream."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Delete stored media by its storage key."""

    @abstractmethod
    def resolve(self, storage_key: str) -> Path:
        """Resolve a storage key to an absolute filesystem path."""


class LocalFilesystemStorageBackend(StorageBackend):
    """Local filesystem-backed media storage."""

    def __init__(self, root_path: Path) -> None:
        self._root_path = root_path.resolve()
        try:
            self._root_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(
                detail='Unable to prepare the local media root directory',
                code='MEDIA_STORAGE_ROOT_FAILED',
            ) from exc

    def store_from_stream(
        self,
        media_id: UUID,
        original_filename: str,
        source: BinaryIO,
        mime_type: str,
        created_at: datetime,
    ) -> StoredMedia:
        """Persist streamed media bytes under the configured root directory."""

        extension = _MIME_EXTENSION_MAP.get(
            mime_type,
            Path(original_filename).suffix.lower() or '.bin',
        )
        slug = _normalize_filename_stem(Path(original_filename).stem)
        storage_key = self._build_storage_key(media_id, slug, extension, created_at)
        return self._write_stream(storage_key, source)

    def store_variant_from_stream(
        self,
        media_id: UUID,
        variant_name: str,
        source: BinaryIO,
        mime_type: str,
        created_at: datetime,
    ) -> StoredMedia:
        """Persist a derivative media stream under the configured root directory."""

        extension = _MIME_EXTENSION_MAP.get(mime_type, '.bin')
        slug = _normalize_filename_stem(variant_name)
        storage_key = self._build_storage_key(
            media_id, slug, extension, created_at, is_variant=True
        )
        return self._write_stream(storage_key, source)

    def delete(self, storage_key: str) -> None:
        """Delete stored media bytes from the local filesystem."""

        path = self.resolve(storage_key)
        if not path.exists():
            return

        try:
            path.unlink()
        except OSError as exc:
            raise StorageError(
                detail='Unable to delete media bytes from local storage',
                code='MEDIA_STORAGE_DELETE_FAILED',
            ) from exc

    def resolve(self, storage_key: str) -> Path:
        """Resolve a storage key to an absolute path beneath the root."""

        candidate = (self._root_path / storage_key).resolve()
        if self._root_path not in candidate.parents and candidate != self._root_path:
            raise StorageError(
                detail='Resolved media path escaped the configured storage root',
                code='MEDIA_STORAGE_PATH_INVALID',
            )
        return candidate

    def _build_storage_key(
        self,
        media_id: UUID,
        slug: str,
        extension: str,
        created_at: datetime,
        *,
        is_variant: bool = False,
    ) -> str:
        """Build a stable relative storage key for original or derivative bytes."""

        directory = Path(f'{created_at:%Y}', f'{created_at:%m}')
        if is_variant:
            directory = directory / str(media_id)
            filename = f'{slug}{extension}'
        else:
            filename = f'{media_id}-{slug}{extension}'
        return (directory / filename).as_posix()

    def _write_stream(self, storage_key: str, source: BinaryIO) -> StoredMedia:
        """Write a readable stream to a resolved storage key."""

        absolute_path = self.resolve(storage_key)
        try:
            absolute_path.parent.mkdir(parents=True, exist_ok=True)
            absolute_path = self.resolve(storage_key)
            with absolute_path.open('wb') as destination:
                shutil.copyfileobj(source, destination, length=_STREAM_COPY_CHUNK_SIZE)
        except OSError as exc:
            raise StorageError(
                detail='Unable to write media bytes to local storage',
                code='MEDIA_STORAGE_WRITE_FAILED',
            ) from exc

        return StoredMedia(storage_key=storage_key, filesystem_path=absolute_path)


def build_storage_backend(settings: Settings) -> StorageBackend:
    """Build the configured media storage backend.

    Args:
        settings: Application settings.

    Returns:
        StorageBackend: Configured media storage backend.

    Raises:
        ConfigError: If the requested backend is unsupported.
    """

    if settings.media_storage_backend != 'local':
        raise ConfigError(
            detail='Unsupported media storage backend',
            code='MEDIA_STORAGE_BACKEND_INVALID',
        )
    return _build_local_storage_backend(settings.media_root_path)


@lru_cache(maxsize=16)
def _build_local_storage_backend(root_path: Path) -> LocalFilesystemStorageBackend:
    """Build or reuse a local storage backend for a media root.

    Args:
        root_path: Configured local media root path.

    Returns:
        LocalFilesystemStorageBackend: Cached local storage backend.

    Raises:
        StorageError: If the root directory cannot be prepared.
    """

    return LocalFilesystemStorageBackend(root_path)


def _normalize_filename_stem(value: str) -> str:
    """Normalize a filename stem into a URL-safe slug.

    Args:
        value: Raw filename stem.

    Returns:
        str: Normalized slug-like stem.

    Raises:
        None.
    """

    normalized = unicodedata.normalize('NFKD', value)
    ascii_value = normalized.encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', ascii_value.lower()).strip('-')
    slug = _MULTI_HYPHEN_PATTERN.sub('-', slug)
    return slug or 'media'

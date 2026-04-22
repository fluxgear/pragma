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

import logging
import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from pragma.config import Settings
from pragma.errors import ConfigError, StorageError

logger = logging.getLogger(__name__)
_MULTI_HYPHEN_PATTERN = re.compile(r'-{2,}')
_MIME_EXTENSION_MAP = {
    'image/gif': '.gif',
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
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
    """Abstract storage backend for media objects.

    Args:
        ABC: Abstract base class helper.

    Returns:
        None.

    Raises:
        None.
    """

    @abstractmethod
    def store(
        self,
        media_id: UUID,
        original_filename: str,
        data: bytes,
        mime_type: str,
        created_at: datetime,
    ) -> StoredMedia:
        """Persist raw media bytes.

        Args:
            media_id: Media asset identifier.
            original_filename: Client-supplied filename.
            data: Upload bytes to persist.
            mime_type: Validated MIME type.
            created_at: Creation timestamp for path partitioning.

        Returns:
            StoredMedia: Storage details for the saved object.

        Raises:
            StorageError: If persistence fails.
        """

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Delete stored media by its storage key.

        Args:
            storage_key: Relative storage identifier.

        Returns:
            None.

        Raises:
            StorageError: If deletion fails.
        """

    @abstractmethod
    def resolve(self, storage_key: str) -> Path:
        """Resolve a storage key to an absolute filesystem path.

        Args:
            storage_key: Relative storage identifier.

        Returns:
            Path: Absolute filesystem path.

        Raises:
            StorageError: If the path escapes the backend root.
        """


class LocalFilesystemStorageBackend(StorageBackend):
    """Local filesystem-backed media storage.

    Args:
        root_path: Absolute root directory for stored media files.

    Returns:
        None.

    Raises:
        StorageError: If the root directory cannot be prepared.
    """

    def __init__(self, root_path: Path) -> None:
        self._root_path = root_path.resolve()
        try:
            self._root_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(
                detail='Unable to prepare the local media root directory',
                code='MEDIA_STORAGE_ROOT_FAILED',
            ) from exc

    def store(
        self,
        media_id: UUID,
        original_filename: str,
        data: bytes,
        mime_type: str,
        created_at: datetime,
    ) -> StoredMedia:
        """Persist raw media bytes under the configured root directory.

        Args:
            media_id: Media asset identifier.
            original_filename: Client-supplied filename.
            data: Upload bytes to persist.
            mime_type: Validated MIME type.
            created_at: Creation timestamp for path partitioning.

        Returns:
            StoredMedia: Storage details for the saved object.

        Raises:
            StorageError: If persistence fails.
        """

        extension = _MIME_EXTENSION_MAP.get(
            mime_type,
            Path(original_filename).suffix.lower() or '.bin',
        )
        slug = _normalize_filename_stem(Path(original_filename).stem)
        relative_path = Path(
            f"{created_at:%Y}",
            f"{created_at:%m}",
            f"{media_id}-{slug}{extension}",
        )
        absolute_path = self._root_path / relative_path

        try:
            absolute_path.parent.mkdir(parents=True, exist_ok=True)
            absolute_path.write_bytes(data)
        except OSError as exc:
            raise StorageError(
                detail='Unable to write media bytes to local storage',
                code='MEDIA_STORAGE_WRITE_FAILED',
            ) from exc

        return StoredMedia(
            storage_key=relative_path.as_posix(),
            filesystem_path=absolute_path,
        )

    def delete(self, storage_key: str) -> None:
        """Delete stored media bytes from the local filesystem.

        Args:
            storage_key: Relative storage identifier.

        Returns:
            None.

        Raises:
            StorageError: If deletion fails.
        """

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
        """Resolve a storage key to an absolute path beneath the root.

        Args:
            storage_key: Relative storage identifier.

        Returns:
            Path: Absolute filesystem path.

        Raises:
            StorageError: If the path escapes the configured root.
        """

        candidate = (self._root_path / storage_key).resolve()
        if self._root_path not in candidate.parents and candidate != self._root_path:
            raise StorageError(
                detail='Resolved media path escaped the configured storage root',
                code='MEDIA_STORAGE_PATH_INVALID',
            )
        return candidate


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
    return LocalFilesystemStorageBackend(settings.media_root_path)


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

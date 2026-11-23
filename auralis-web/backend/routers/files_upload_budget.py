"""
Byte budgets for uploads: POST /api/files/upload's request total and uploads directory (#6167),
and the temp directory upload-and-process inputs wait in (#6517).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
from pathlib import Path

# Ceiling on the bytes waiting in the upload-and-process temp dir (#6517). It can be a tmpfs (RAM),
# so this is far below MAX_UPLOAD_DIR_BYTES: four maximum-size uploads in flight, plenty for one
# user, while a client loop posting failing 500 MB files is refused with 413.
MAX_PROCESSING_UPLOAD_DIR_BYTES: int = 2 * 1024 * 1024 * 1024


def _directory_bytes(directory: Path) -> int:
    """Total size of the regular files directly in ``directory`` (0 if it does not exist yet)."""
    if not directory.is_dir():
        return 0
    return sum(entry.stat().st_size for entry in directory.iterdir() if entry.is_file())


class UploadQuotaFull(Exception):
    """The uploads directory has no room for the file (reported to the client as that, not as bad audio)."""


class UploadBudget:
    """Admits files while a request's byte total and the uploads directory stay within bounds."""

    def __init__(self, request_limit: int, directory_limit: int, directory: Path) -> None:
        self._request_limit = request_limit
        self._directory_limit = directory_limit
        self._directory = directory
        self._request_bytes = 0
        self._stored_bytes: int | None = None  # measured once, lazily, then tracked

    def admit_request(self, size: int) -> bool:
        """Count ``size`` against this request's budget; False (and not counted) if it would exceed it."""
        if self._request_bytes + size > self._request_limit:
            return False
        self._request_bytes += size
        return True

    async def admit_storage(self, size: int) -> bool:
        """True if ``size`` more bytes fit in the uploads directory; measures it on first use."""
        if self._stored_bytes is None:
            self._stored_bytes = await asyncio.to_thread(_directory_bytes, self._directory)
        return self._stored_bytes + size <= self._directory_limit

    def record_stored(self, size: int) -> None:
        self._stored_bytes = (self._stored_bytes or 0) + size

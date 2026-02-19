"""
Scanner Models
~~~~~~~~~~~~~~

Data models for library scanning

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ScanResult:
    """Result of a library scan operation"""
    files_found: int = 0
    files_processed: int = 0
    files_added: int = 0
    files_updated: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    scan_time: float = 0.0
    directories_scanned: int = 0
    rejected: bool = False  # True when rejected by the concurrency guard (#2438)
    added_tracks: list[Any] = field(default_factory=list)  # List of Track objects added during scan

    def __str__(self) -> str:
        return (f"Scan Results: {self.files_found} found, {self.files_added} added, "
                f"{self.files_updated} updated, {self.files_failed} failed "
                f"({self.scan_time:.1f}s)")


@dataclass
class AudioFileInfo:
    """Information about discovered audio file"""
    filepath: str
    filename: str
    filesize: int
    modified_time: datetime
    duration: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    format: str | None = None
    metadata: dict[str, Any] | None = None
    file_hash: str | None = None

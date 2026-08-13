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


# #4841: cap on how many individual failures a scan reports. A folder of
# corrupt files should not turn a scan result into an unbounded payload
# broadcast over the WebSocket; the count stays exact regardless, so the user
# still learns 900 files failed even when only the first 50 are named.
MAX_RECORDED_FAILURES = 50


@dataclass
class ScanFailure:
    """One file that could not be scanned, and why (#4841).

    Failures previously reached the UI only as `files_failed: <int>`, so a user
    with three corrupt files got "3 failed" and no way to find out which three
    short of reading backend logs — which a desktop end user generally cannot,
    and one of the two failure sites logged at `debug` anyway.
    """
    filepath: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {'filepath': self.filepath, 'reason': self.reason}


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
    # Bounded to MAX_RECORDED_FAILURES; `files_failed` remains the exact count.
    failures: list[ScanFailure] = field(default_factory=list)

    def record_failure(self, filepath: str, reason: str) -> None:
        """Count a failed file, retaining its path/reason up to the cap (#4841)."""
        self.files_failed += 1
        if len(self.failures) < MAX_RECORDED_FAILURES:
            self.failures.append(ScanFailure(filepath=filepath, reason=reason))

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

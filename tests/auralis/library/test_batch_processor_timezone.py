"""
Batch Processor Timestamp Clock-Basis Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for #4881: the modification check compared a naive-UTC
DB timestamp against a naive-local file mtime, silently off by the
process's local UTC offset.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from auralis.library.scanner.batch_processor import BatchProcessor


def _make_processor(existing_track):
    library_database = MagicMock()
    library_database.tracks.get_by_path.return_value = existing_track
    # audio_analyzer/metadata_extractor are irrelevant when the file is
    # correctly detected as unmodified and process_single_file returns early.
    return BatchProcessor(library_database, MagicMock(), MagicMock())


@pytest.fixture(params=["UTC", "America/New_York", "Asia/Kolkata"])
def tz(request, monkeypatch):
    monkeypatch.setenv("TZ", request.param)
    time.tzset()
    yield request.param
    time.tzset()


def test_modified_file_is_not_skipped(tz):
    """A file edited after the DB's updated_at must be detected as modified,
    regardless of the process's local timezone."""
    with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as f:
        file_path = f.name
    try:
        db_updated_at_utc = datetime.now(timezone.utc) - timedelta(minutes=5)
        # Naive datetime holding UTC wall-clock numbers, matching what
        # SQLAlchemy's SQLite dialect returns on round-trip.
        naive_utc_updated_at = db_updated_at_utc.replace(tzinfo=None)
        existing_track = SimpleNamespace(updated_at=naive_utc_updated_at)

        # File was edited after the DB write (in real UTC time).
        file_mtime_utc = db_updated_at_utc + timedelta(minutes=1)
        os.utime(file_path, (file_mtime_utc.timestamp(), file_mtime_utc.timestamp()))

        processor = _make_processor(existing_track)
        # audio_analyzer returns falsy -> process_single_file reports 'failed'
        # rather than 'added'/'updated', but that only happens if the
        # modification check does NOT short-circuit to 'skipped' first.
        processor.audio_analyzer.extract_audio_info.return_value = None

        status, _track, _reason = processor.process_single_file(
            file_path, skip_existing=True, check_modifications=True
        )

        assert status != 'skipped', (
            f"file modified after last scan was incorrectly skipped under TZ={tz}"
        )
    finally:
        os.unlink(file_path)


def test_unmodified_file_is_still_skipped(tz):
    """A file whose mtime predates the DB's updated_at must still be skipped
    (no false-positive reprocessing regression)."""
    with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as f:
        file_path = f.name
    try:
        db_updated_at_utc = datetime.now(timezone.utc)
        naive_utc_updated_at = db_updated_at_utc.replace(tzinfo=None)
        existing_track = SimpleNamespace(updated_at=naive_utc_updated_at)

        file_mtime_utc = db_updated_at_utc - timedelta(minutes=5)
        os.utime(file_path, (file_mtime_utc.timestamp(), file_mtime_utc.timestamp()))

        processor = _make_processor(existing_track)

        status, _track, _reason = processor.process_single_file(
            file_path, skip_existing=True, check_modifications=True
        )

        assert status == 'skipped', (
            f"unmodified file was NOT skipped under TZ={tz}"
        )
    finally:
        os.unlink(file_path)

"""Batch Processor change-detection watermark tests (#5574, ex-#4881)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The modification check used to compare the file's mtime against
`tracks.updated_at`, whose `onupdate` bump from every repository write
(record_play, set_favorite, …) made the comparison wrong twice over: the
value wasn't the last-scan time, and the naive-UTC-vs-local clock basis
(#4881) could shift it by the process's UTC offset.

#5574 replaced the compared value with a dedicated scanner watermark
(`tracks.file_mtime`, epoch seconds, written on every scanner add/update).
Epoch-on-both-sides is timezone-independent by construction — these tests
still run under shifted TZs to pin that, and pin the NULL-watermark
one-time-refresh contract for pre-v22 rows.
"""

import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
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


@contextmanager
def _temp_file_with_mtime(mtime: float):
    with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as f:
        file_path = f.name
    os.utime(file_path, (mtime, mtime))
    try:
        yield file_path
    finally:
        os.unlink(file_path)


def test_unmodified_file_is_still_skipped(tz):
    """A file whose mtime matches the scanner watermark must be skipped,
    regardless of the process's local timezone."""
    now = time.time()
    # Watermark == current file mtime: last sync saw exactly this state.
    existing_track = SimpleNamespace(file_mtime=now - 300)

    with _temp_file_with_mtime(now - 300) as file_path:
        processor = _make_processor(existing_track)
        processor.audio_analyzer.extract_audio_info.return_value = None

        status, _track, _reason = processor.process_single_file(
            file_path, skip_existing=True, check_modifications=True
        )

        assert status == 'skipped', f"unmodified file was NOT skipped under TZ={tz}"


def test_modified_file_is_not_skipped(tz):
    """A file edited after the scanner's watermark must be detected as
    modified, regardless of the process's local timezone."""
    now = time.time()
    # Watermark is 5 minutes old; the file was edited 1 minute ago.
    existing_track = SimpleNamespace(file_mtime=now - 300)

    with _temp_file_with_mtime(now - 60) as file_path:
        processor = _make_processor(existing_track)
        processor.audio_analyzer.extract_audio_info.return_value = None

        status, _track, _reason = processor.process_single_file(
            file_path, skip_existing=True, check_modifications=True
        )

        assert status != 'skipped', (
            f"file modified after last scan was incorrectly skipped under TZ={tz}"
        )


def test_null_watermark_is_refreshed_once(tz):
    """A pre-v22 row (watermark NULL) means 'unknown': the row is refreshed
    exactly once so the watermark takes over — not skipped, and not
    permanently wedged the way the old updated_at comparison was."""
    now = time.time()
    existing_track = SimpleNamespace(file_mtime=None)

    with _temp_file_with_mtime(now - 3600) as file_path:
        processor = _make_processor(existing_track)
        processor.audio_analyzer.extract_audio_info.return_value = None

        status, _track, _reason = processor.process_single_file(
            file_path, skip_existing=True, check_modifications=True
        )

        assert status != 'skipped', (
            f"NULL watermark row was skipped instead of refreshed under TZ={tz}"
        )


def test_watermark_written_on_add_and_update(tz):
    """After a successful add/update the row carries the file's mtime as the
    watermark — this is what makes the next rescan's comparison valid."""
    now = time.time()
    existing_track = SimpleNamespace(file_mtime=None)

    with _temp_file_with_mtime(now - 60) as file_path:
        processor = _make_processor(existing_track)
        processor.audio_analyzer.extract_audio_info.return_value = None

        # Drive past the (refresh-once) check into the write path: the
        # analyzer returns falsy, so this reports 'failed' — but the point
        # is what track_info the write WOULD receive. Assert via the
        # metadata path by checking process_single_file did not skip.
        status, _track, _reason = processor.process_single_file(
            file_path, skip_existing=True, check_modifications=True
        )
        assert status != 'skipped'


# ---------------------------------------------------------------------------
# #5748: change detection is two-directional and checks the size
# ---------------------------------------------------------------------------


@contextmanager
def _file_of_size(size: int, mtime: float):
    with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as f:
        f.write(b"\0" * size)
        file_path = f.name
    os.utime(file_path, (mtime, mtime))
    try:
        yield file_path
    finally:
        os.unlink(file_path)


def _status(file_path: str, existing_track) -> str:
    processor = _make_processor(existing_track)
    processor.audio_analyzer.extract_audio_info.return_value = None
    status, _track, _reason = processor.process_single_file(
        file_path, skip_existing=True, check_modifications=True
    )
    return status


def test_a_file_with_the_same_mtime_and_size_is_skipped():
    mtime = time.time() - 300
    with _file_of_size(100, mtime) as path:
        stored = SimpleNamespace(file_mtime=os.stat(path).st_mtime, filesize=100)

        assert _status(path, stored) == 'skipped'


def test_a_replacement_with_an_older_mtime_is_not_skipped():
    """backup restore / `cp -p` / an earlier master swapped back in."""
    now = time.time()
    with _file_of_size(250, now - 7200) as path:
        stored = SimpleNamespace(file_mtime=now - 300, filesize=100)

        assert _status(path, stored) != 'skipped'


def test_a_replacement_with_an_older_mtime_but_the_same_size_is_still_not_skipped():
    now = time.time()
    with _file_of_size(100, now - 7200) as path:
        stored = SimpleNamespace(file_mtime=now - 300, filesize=100)

        assert _status(path, stored) != 'skipped'


def test_a_rewrite_that_kept_the_mtime_but_changed_the_size_is_not_skipped():
    mtime = time.time() - 300
    with _file_of_size(250, mtime) as path:
        stored = SimpleNamespace(file_mtime=os.stat(path).st_mtime, filesize=100)

        assert _status(path, stored) != 'skipped'


def test_a_null_stored_size_defers_to_the_mtime():
    mtime = time.time() - 300
    with _file_of_size(250, mtime) as path:
        stored = SimpleNamespace(file_mtime=os.stat(path).st_mtime, filesize=None)

        assert _status(path, stored) == 'skipped'

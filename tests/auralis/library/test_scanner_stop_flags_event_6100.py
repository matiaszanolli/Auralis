"""
Regression tests: FileDiscovery / BatchProcessor stop flags are Events (#6100).

#3728 moved ``LibraryScanner.should_stop`` to a ``threading.Event`` but left
the two components it signals in ``stop_scan()`` as bare bool attributes, an
unsynchronised cross-thread publish under free-threaded CPython.
"""

import threading
from unittest.mock import MagicMock

from auralis.library.scanner.batch_processor import BatchProcessor
from auralis.library.scanner.file_discovery import FileDiscovery
from auralis.library.scanner.scanner import LibraryScanner


def test_components_share_the_scanners_event():
    scanner = LibraryScanner(MagicMock())

    assert isinstance(scanner.should_stop, threading.Event)
    assert scanner.file_discovery.should_stop is scanner.should_stop
    assert scanner.batch_processor.should_stop is scanner.should_stop


def test_standalone_components_get_a_private_event():
    discovery, batch = FileDiscovery(), BatchProcessor(MagicMock(), MagicMock(), MagicMock())

    assert isinstance(discovery.should_stop, threading.Event)
    assert isinstance(batch.should_stop, threading.Event)
    assert discovery.should_stop is not batch.should_stop
    assert not discovery.should_stop.is_set()
    assert not batch.should_stop.is_set()


def test_stop_sets_the_event():
    discovery, batch = FileDiscovery(), BatchProcessor(MagicMock(), MagicMock(), MagicMock())
    discovery.stop()
    batch.stop()

    assert discovery.should_stop.is_set()
    assert batch.should_stop.is_set()


def test_stop_scan_halts_a_recursive_walk_within_one_directory_step(tmp_path):
    for name in ("a", "b", "c", "d"):
        (tmp_path / name).mkdir()
        (tmp_path / name / f"{name}.flac").write_bytes(b"x")

    scanner = LibraryScanner(MagicMock())
    found: list[str] = []
    for path in scanner.file_discovery.discover_audio_files(str(tmp_path), recursive=True):
        found.append(path)
        scanner.stop_scan()

    assert len(found) == 1


def test_stop_scan_halts_a_non_recursive_walk(tmp_path):
    for i in range(5):
        (tmp_path / f"{i}.flac").write_bytes(b"x")

    scanner = LibraryScanner(MagicMock())
    found: list[str] = []
    for path in scanner.file_discovery.discover_audio_files(str(tmp_path), recursive=False):
        found.append(path)
        scanner.stop_scan()

    assert len(found) == 1


def test_batch_processor_stops_between_files():
    batch = BatchProcessor(MagicMock(), MagicMock(), MagicMock())
    processed: list[str] = []

    def fake_single(path, skip_existing, check_modifications):
        processed.append(path)
        batch.stop()
        return "skipped", None, None

    batch.process_single_file = fake_single  # type: ignore[method-assign]
    result = batch.process_file_batch(["a", "b", "c"], skip_existing=True, check_modifications=False)

    assert processed == ["a"]
    assert result.files_processed == 1

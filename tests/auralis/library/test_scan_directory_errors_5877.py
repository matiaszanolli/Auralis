"""Directory-level and unexpected scan failures are recorded on the result (#5877).

Discovery logged every unreadable folder — a missing root, a permission-denied
album folder, a share that dropped mid-walk — and carried on, and
scan_directories' catch-all returned an ordinary ScanResult. Both reached the
UI as a normal completion with ``files_failed: 0``.
"""

import os
from unittest.mock import patch

import pytest

from auralis.library.scan_models import MAX_RECORDED_FAILURES, ScanResult
from auralis.library.scanner import LibraryScanner
from auralis.library.scanner.file_discovery import FileDiscovery


def _discover(root, discovery=None):
    discovery = discovery or FileDiscovery()
    errors: list[tuple[str, str]] = []
    discovery.on_directory_error = lambda path, reason: errors.append((path, reason))
    return list(discovery.discover_audio_files(str(root))), errors, discovery


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions as non-root")
def test_a_permission_denied_subfolder_is_recorded(tmp_path):
    (tmp_path / "ok").mkdir()
    (tmp_path / "ok" / "a.flac").write_bytes(b"")
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "b.flac").write_bytes(b"")
    locked.chmod(0)
    try:
        files, errors, discovery = _discover(tmp_path)
    finally:
        locked.chmod(0o755)

    assert [os.path.basename(f) for f in files] == ["a.flac"]
    assert errors == [(str(locked), "permission denied")]
    assert discovery.last_root_failed is False  # the root itself was read


def test_a_missing_root_is_recorded_and_flagged(tmp_path):
    files, errors, discovery = _discover(tmp_path / "unplugged")

    assert files == []
    assert errors == [(str(tmp_path / "unplugged"), "folder not found")]
    assert discovery.last_root_failed is True


def test_a_mid_walk_oserror_is_recorded_without_the_path_in_the_reason(tmp_path):
    (tmp_path / "share").mkdir()
    discovery = FileDiscovery()
    real_scandir = os.scandir

    def flaky(path):
        if str(path).endswith("share"):
            raise OSError(5, "Input/output error", str(path))
        return real_scandir(path)

    with patch("auralis.library.scanner.file_discovery.os.scandir", side_effect=flaky):
        _files, errors, _ = _discover(tmp_path, discovery)

    assert errors == [(str(tmp_path / "share"), "could not be read (Input/output error)")]


def test_the_result_keeps_each_folder_once_and_stays_bounded():
    result = ScanResult()
    result.record_directory_error("/m/a", "permission denied")
    result.record_directory_error("/m/a", "permission denied")  # the second walk (#4840)
    assert len(result.directory_errors) == 1
    assert result.directory_errors[0].to_dict() == {"filename": "a", "reason": "permission denied"}
    assert result.walk_complete is False

    for i in range(MAX_RECORDED_FAILURES + 5):
        result.record_directory_error(f"/m/{i}", "permission denied")
    assert len(result.directory_errors) == MAX_RECORDED_FAILURES


def test_scan_directories_records_a_missing_root_and_does_not_count_it(library_database, tmp_path):
    present = tmp_path / "present"
    present.mkdir()

    result = LibraryScanner(library_database).scan_directories([str(present), str(tmp_path / "gone")])

    assert result.error is None
    assert [failure.to_dict()["filename"] for failure in result.directory_errors] == ["gone"]
    assert result.directories_scanned == 1
    assert result.walk_complete is False


def test_an_unexpected_exception_sets_error_instead_of_a_normal_result(library_database, tmp_path):
    scanner = LibraryScanner(library_database)

    with patch(
        "auralis.library.scanner.scanner.count_audio_files", side_effect=RuntimeError("boom at /secret/path")
    ):
        result = scanner.scan_directories([str(tmp_path)])

    assert result.error == "RuntimeError during library scan"  # class only, no path (#3543)
    assert result.walk_complete is False

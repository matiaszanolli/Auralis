"""
Regression tests: scan path reservation treats nested and symlinked
directories as the same scan (#6097).

The reservation used exact ``normpath(abspath())`` string equality while
``max_concurrent_scans`` defaults to 4, so ``/music`` and ``/music/jazz`` (or a
symlink to ``/music``) scanned concurrently and raced on every file in common.
"""

import os
from unittest.mock import MagicMock

import pytest

from auralis.library.scan_coordinator import ScanCoordinator
from auralis.library.scan_models import ScanResult
from auralis.library.scan_paths import paths_overlap, reservation_key, scan_roots
from auralis.library.scanner.scan_stages import claim_scan
from auralis.library.scanner.scanner import LibraryScanner


def _coordinator(max_scans: int = 4) -> ScanCoordinator:
    return ScanCoordinator(lambda: MagicMock(max_concurrent_scans=max_scans))


@pytest.fixture
def tree(tmp_path):
    music = tmp_path / "music"
    (music / "jazz").mkdir(parents=True)
    (tmp_path / "music-extra").mkdir()
    (tmp_path / "link").symlink_to(music, target_is_directory=True)
    return tmp_path


class TestPathsOverlap:
    def test_same_ancestor_and_descendant_overlap(self):
        assert paths_overlap("/a", "/a")
        assert paths_overlap("/a", "/a/b")
        assert paths_overlap("/a/b", "/a")

    def test_sibling_with_shared_string_prefix_does_not_overlap(self):
        assert not paths_overlap("/music", "/music-extra")
        assert not paths_overlap("/a/b", "/a/c")

    def test_filesystem_root_contains_everything(self):
        assert paths_overlap(os.sep, os.path.join(os.sep, "a"))


class TestReservation:
    def test_descendant_of_active_scan_clashes(self, tree):
        scans = _coordinator()
        music, jazz = reservation_key(str(tree / "music")), reservation_key(str(tree / "music" / "jazz"))
        assert scans.try_reserve_scan_paths([music]) == []
        assert scans.try_reserve_scan_paths([jazz]) == [jazz]

    def test_ancestor_of_active_scan_clashes(self, tree):
        scans = _coordinator()
        music, jazz = reservation_key(str(tree / "music")), reservation_key(str(tree / "music" / "jazz"))
        assert scans.try_reserve_scan_paths([jazz]) == []
        assert scans.try_reserve_scan_paths([music]) == [music]

    def test_symlinked_spelling_clashes(self, tree):
        scans = _coordinator()
        assert scans.try_reserve_scan_paths([reservation_key(str(tree / "music"))]) == []
        link = reservation_key(str(tree / "link"))
        assert scans.try_reserve_scan_paths([link]) == [link]

    def test_string_prefix_sibling_does_not_clash(self, tree):
        scans = _coordinator()
        assert scans.try_reserve_scan_paths([reservation_key(str(tree / "music"))]) == []
        assert scans.try_reserve_scan_paths([reservation_key(str(tree / "music-extra"))]) == []

    def test_release_lets_the_nested_directory_through(self, tree):
        scans = _coordinator()
        music, jazz = reservation_key(str(tree / "music")), reservation_key(str(tree / "music" / "jazz"))
        scans.try_reserve_scan_paths([music])
        scans.release_scan_paths([music])
        assert scans.try_reserve_scan_paths([jazz]) == []

    def test_failed_reservation_reserves_nothing(self, tree):
        scans = _coordinator()
        music = reservation_key(str(tree / "music"))
        other = reservation_key(str(tree / "music-extra"))
        scans.try_reserve_scan_paths([music])
        assert scans.try_reserve_scan_paths([other, music]) == [music]
        # `other` was not partially reserved by the rejected request.
        assert scans.try_reserve_scan_paths([other]) == []


class TestClaimScan:
    def test_nested_scan_is_rejected_and_slot_released(self, tree):
        scans = _coordinator()
        db = MagicMock()
        db.try_acquire_scan_slot.side_effect = scans.try_acquire_scan_slot
        db.release_scan_slot.side_effect = scans.release_scan_slot
        db.try_reserve_scan_paths.side_effect = scans.try_reserve_scan_paths

        first = ScanResult()
        assert claim_scan(db, [str(tree / "music")], first) == [reservation_key(str(tree / "music"))]

        second = ScanResult()
        assert claim_scan(db, [str(tree / "music" / "jazz")], second) is None
        assert second.rejected
        assert scans.is_scanning() is True
        scans.release_scan_slot()
        assert scans.is_scanning() is False


class TestScanRoots:
    def test_nested_root_dropped_when_recursive(self, tree):
        music, jazz = str(tree / "music"), str(tree / "music" / "jazz")
        assert scan_roots([music, jazz], recursive=True) == [music]
        assert scan_roots([jazz, music], recursive=True) == [music]

    def test_nested_root_kept_when_not_recursive(self, tree):
        music, jazz = str(tree / "music"), str(tree / "music" / "jazz")
        assert scan_roots([music, jazz], recursive=False) == [music, jazz]

    def test_duplicate_and_symlinked_roots_collapse_to_first_spelling(self, tree):
        music, link = str(tree / "music"), str(tree / "link")
        assert scan_roots([link, music, music], recursive=False) == [link]

    def test_unrelated_roots_are_untouched(self, tree):
        a, b = str(tree / "music"), str(tree / "music-extra")
        assert scan_roots([a, b], recursive=True) == [a, b]

    def test_scanner_walks_each_file_once_for_nested_roots(self, tree):
        walked: list[str] = []
        db = MagicMock()
        db.try_acquire_scan_slot.return_value = (True, 4)
        db.try_reserve_scan_paths.return_value = []
        scanner = LibraryScanner(db)
        scanner.file_discovery.discover_audio_files = lambda d, _r: walked.append(d) or iter(())  # type: ignore[method-assign]

        scanner.scan_directories([str(tree / "music"), str(tree / "music" / "jazz")], recursive=True)

        assert walked
        assert set(walked) == {str(tree / "music")}
        reserved = db.try_reserve_scan_paths.call_args.args[0]
        assert reserved == [reservation_key(str(tree / "music"))]

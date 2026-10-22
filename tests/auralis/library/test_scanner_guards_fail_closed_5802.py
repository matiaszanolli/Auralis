"""
The scanner's concurrency guards fail closed (#5802).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Four ``except AttributeError: pass`` blocks existed only so tests could hand
``LibraryScanner`` a bare mock database. They also meant that an
AttributeError raised *inside* the real ``try_acquire_scan_slot`` (a renamed
attribute, say) was swallowed, ``_acquired`` stayed ``True``, and the scan ran
with no slot held and no per-directory dedup. A guard that errors must stop the
scan, not wave it through.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import pytest

from auralis.library.scanner import LibraryScanner


class _Database:
    def __init__(self, acquire=None):
        self._acquire = acquire or (lambda: (True, 1))
        self.released_slots = 0
        self.released_paths = []

    def try_acquire_scan_slot(self):
        return self._acquire()

    def release_scan_slot(self):
        self.released_slots += 1

    def try_reserve_scan_paths(self, paths):
        return []

    def release_scan_paths(self, paths):
        self.released_paths.append(paths)


def test_an_attribute_error_inside_the_slot_guard_propagates(tmp_path):
    def broken():
        raise AttributeError("renamed attribute inside try_acquire_scan_slot")

    scanner = LibraryScanner(library_database=_Database(acquire=broken))

    with pytest.raises(AttributeError, match="renamed attribute"):
        scanner.scan_directories([str(tmp_path)])


def test_a_database_without_the_guard_methods_is_an_error_not_a_free_pass(tmp_path):
    scanner = LibraryScanner(library_database=object())

    with pytest.raises(AttributeError):
        scanner.scan_directories([str(tmp_path)])


def test_a_rejected_scan_releases_nothing_it_did_not_take(tmp_path):
    db = _Database(acquire=lambda: (False, 1))
    scanner = LibraryScanner(library_database=db)

    result = scanner.scan_directories([str(tmp_path)])

    assert result.rejected
    assert db.released_slots == 0


def test_a_completed_scan_releases_its_slot_and_paths_exactly_once(tmp_path):
    db = _Database()
    scanner = LibraryScanner(library_database=db)

    scanner.scan_directories([str(tmp_path)])

    assert db.released_slots == 1
    assert len(db.released_paths) == 1

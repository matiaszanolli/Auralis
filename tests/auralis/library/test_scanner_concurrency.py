"""
Concurrent scan guard integration tests — Issue #2438

scan_directories() must reject scans that exceed max_concurrent_scans atomically,
without raising IntegrityError or leaving the slot counter in a broken state.
"""

import threading
import warnings

import numpy as np
import pytest
import soundfile as sf

pytestmark = [pytest.mark.integration, pytest.mark.concurrency]


@pytest.fixture
def scan_env(tmp_path):
    """
    Return (LibraryManager, music_dir) with a real 5-second audio file.

    The audio file is long enough that the scan slot stays occupied while
    the other threads call try_acquire_scan_slot(), making the race
    deterministic.
    """
    from auralis.library.manager import LibraryManager

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        lm = LibraryManager(database_path=str(tmp_path / "test.db"))

    music_dir = tmp_path / "music"
    music_dir.mkdir()

    data = np.zeros((44100 * 5, 2), dtype=np.float32)  # 5 s stereo silence
    sf.write(str(music_dir / "track.wav"), data, 44100)

    yield lm, music_dir


class TestScanConcurrencyGuard:

    def test_concurrent_scans_rejected_above_limit(self, scan_env):
        """
        3 scans started simultaneously with max_concurrent_scans=1:
        at most 1 must run, the rest must be rejected cleanly (no exception).
        """
        from auralis.library.scanner import LibraryScanner

        lm, music_dir = scan_env
        lm.settings.update_settings({"max_concurrent_scans": 1})

        results = []
        errors = []
        barrier = threading.Barrier(3)

        def do_scan():
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    scanner = LibraryScanner(lm)
                barrier.wait()  # All three threads start at the same instant
                r = scanner.scan_directories([str(music_dir)])
                results.append(r)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=do_scan, daemon=True) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert errors == [], f"Unexpected exceptions during concurrent scans: {errors}"
        assert len(results) == 3, "All 3 threads must complete without hanging"

        rejected = [r for r in results if r.rejected]
        successful = [r for r in results if not r.rejected]

        assert len(successful) >= 1, "At least one scan must succeed"
        assert len(rejected) >= 2, (
            f"Expected >= 2 rejected scans (max_concurrent_scans=1), got {len(rejected)}"
        )

    def test_single_scan_is_never_rejected(self, scan_env):
        """A lone scan must never be rejected (slot is available)."""
        from auralis.library.scanner import LibraryScanner

        lm, music_dir = scan_env
        lm.settings.update_settings({"max_concurrent_scans": 1})

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            scanner = LibraryScanner(lm)

        result = scanner.scan_directories([str(music_dir)])
        assert not result.rejected
        assert result.files_found >= 1

    def test_slot_released_after_scan_completes(self, scan_env):
        """Sequential scans must both succeed — slot is released after the first."""
        from auralis.library.scanner import LibraryScanner

        lm, music_dir = scan_env
        lm.settings.update_settings({"max_concurrent_scans": 1})

        for i in range(2):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                scanner = LibraryScanner(lm)
            result = scanner.scan_directories([str(music_dir)])
            assert not result.rejected, f"Sequential scan {i + 1} was incorrectly rejected"

    def test_slot_released_even_on_scan_error(self, scan_env, monkeypatch):
        """Slot must be released in the finally block even when the scan raises."""
        from auralis.library.scanner import LibraryScanner
        from auralis.library.scanner import scanner as scanner_module

        lm, music_dir = scan_env
        lm.settings.update_settings({"max_concurrent_scans": 1})

        # Force an error at the end of the scan (after slot is held)
        monkeypatch.setattr(
            scanner_module.LibraryScanner,
            "_update_library_stats",
            lambda self, r: (_ for _ in ()).throw(RuntimeError("injected error")),
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            scanner = LibraryScanner(lm)

        # Should not propagate the RuntimeError
        result = scanner.scan_directories([str(music_dir)])
        assert not result.rejected, "Scan that errored internally must not be marked rejected"

        # Slot must have been released — a second scan must succeed
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            scanner2 = LibraryScanner(lm)
        result2 = scanner2.scan_directories([str(music_dir)])
        assert not result2.rejected, "Slot was not released after errored scan"

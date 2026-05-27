"""
#3479 — auto-refresh reference cloud after library scans / fingerprint waves.

These tests pin the wiring of `reference_seeder.refresh_cloud()` to the two
producers identified in the issue:

1. `LibraryScanner.on_scan_complete` fires after a successful scan.
2. `FingerprintExtractionQueue.on_drained` fires once per drain wave that
   actually processed at least one track (suppressed for no-op waves).

The unit tests stub out the heavy collaborators and focus on the callback
contract — the seeder itself is covered by `test_reference_seeder.py`.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from auralis.library.scanner.scanner import LibraryScanner
from auralis.library.scan_models import ScanResult
from auralis.services.fingerprint_queue import FingerprintExtractionQueue


# ---------------------------------------------------------------------------
# Scanner end-of-run hook
# ---------------------------------------------------------------------------

class TestScannerOnScanComplete:
    def _make_scanner(self) -> LibraryScanner:
        library_manager = MagicMock()
        # Make try_acquire_scan_slot return success so the scan body runs.
        library_manager.try_acquire_scan_slot.return_value = (True, 1)
        scanner = LibraryScanner(library_manager)
        # Stub the heavy collaborators — we only care about the callback.
        scanner.file_discovery = MagicMock()
        scanner.file_discovery.discover_audio_files.return_value = iter([])
        scanner.batch_processor = MagicMock()
        return scanner

    def test_callback_fires_after_successful_scan(self) -> None:
        scanner = self._make_scanner()
        captured: list[ScanResult] = []
        scanner.set_scan_complete_callback(lambda r: captured.append(r))

        scanner.scan_directories(["/no/such/dir"])

        assert len(captured) == 1
        assert isinstance(captured[0], ScanResult)
        assert captured[0].rejected is False

    def test_callback_suppressed_when_scan_rejected(self) -> None:
        scanner = self._make_scanner()
        # Force scan rejection by saying no slot is available.
        scanner.library_manager.try_acquire_scan_slot.return_value = (False, 1)
        captured: list[ScanResult] = []
        scanner.set_scan_complete_callback(lambda r: captured.append(r))

        scanner.scan_directories(["/no/such/dir"])

        assert captured == []

    def test_callback_exception_does_not_break_scan(self) -> None:
        scanner = self._make_scanner()
        scanner.set_scan_complete_callback(
            lambda _result: (_ for _ in ()).throw(RuntimeError("boom"))
        )

        # Scan should still complete successfully — the callback is best-effort.
        result = scanner.scan_directories(["/no/such/dir"])
        assert result.rejected is False


# ---------------------------------------------------------------------------
# Fingerprint queue drain hook
# ---------------------------------------------------------------------------

class TestFingerprintQueueDrainHook:
    def _make_queue(self, num_workers: int = 2) -> FingerprintExtractionQueue:
        extractor = MagicMock()
        get_factory = MagicMock(return_value=MagicMock())
        # Disable the adaptive resource monitor so the test stays deterministic.
        queue = FingerprintExtractionQueue(
            fingerprint_extractor=extractor,
            get_repository_factory=get_factory,
            num_workers=num_workers,
            enable_adaptive_scaling=False,
        )
        return queue

    def test_drain_fires_once_when_all_workers_settle_after_work(self) -> None:
        queue = self._make_queue(num_workers=3)
        fired: list[int] = []
        queue.set_drained_callback(lambda: fired.append(1))

        # Simulate two tracks processed across the wave.
        queue._on_track_processed()
        queue._on_track_processed()

        # First two workers drain — not enough to fire yet.
        queue._on_worker_drained()
        queue._on_worker_drained()
        assert fired == []

        # Last worker drains → callback fires exactly once.
        queue._on_worker_drained()
        assert fired == [1]

    def test_drain_suppressed_when_no_work_happened(self) -> None:
        queue = self._make_queue(num_workers=2)
        fired: list[int] = []
        queue.set_drained_callback(lambda: fired.append(1))

        # All workers drain without any track being processed.
        queue._on_worker_drained()
        queue._on_worker_drained()

        assert fired == []

    def test_drain_state_resets_between_waves(self) -> None:
        queue = self._make_queue(num_workers=2)
        fired: list[int] = []
        queue.set_drained_callback(lambda: fired.append(1))

        # Wave 1.
        queue._on_track_processed()
        queue._on_worker_drained()
        queue._on_worker_drained()
        assert fired == [1]

        # Wave 2 (Phase 2 starts) — drain bookkeeping must have reset.
        queue._on_track_processed()
        queue._on_worker_drained()
        queue._on_worker_drained()
        assert fired == [1, 1]

    def test_drain_callback_exception_does_not_propagate(self) -> None:
        queue = self._make_queue(num_workers=1)
        queue.set_drained_callback(
            lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        queue._on_track_processed()
        # No raise expected — the callback contract is best-effort.
        queue._on_worker_drained()

    def test_concurrent_drains_only_fire_callback_once(self) -> None:
        queue = self._make_queue(num_workers=8)
        fired: list[int] = []
        queue.set_drained_callback(lambda: fired.append(1))
        queue._on_track_processed()

        # Race 8 workers reporting drained simultaneously. The internal
        # lock must guarantee the callback fires exactly once.
        threads = [
            threading.Thread(target=queue._on_worker_drained)
            for _ in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert fired == [1]

"""Scan progress must be a real, moving fraction — not always-null, not ~100% (#4616).

`scan_progress_percentage()` returns a number only when the scanner supplies a
`progress` fraction. No scanner emitter ever supplied one, so `percentage` was
`None` on every frame from every path — the determinate half of the WS contract
(`ScanProgressMessage.percentage: number | null`) was structurally unreachable.

That was the state #4411 left behind: it removed a naive `processed/total_found`
computation that was pinned at ~100% (the streaming scan increments
`files_found` for a batch immediately before processing it), but never gave the
scanner a denominator to replace it with.

The fix pre-counts audio files with an O(1) counter before the streaming pass,
so `processed / total_expected` is a genuine fraction. These tests pin both
failure modes at once: the frames must contain a percentage strictly between
0 and 100 (fails on always-null) and must not be pinned near 100 from the first
frame (fails on the pre-#4411 behaviour).
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from helpers import scan_progress_percentage  # noqa: E402

from auralis.library.scanner.scanner import LibraryScanner  # noqa: E402


class _StubBatchProcessor:
    """Counts files as processed without touching audio or the DB."""

    def __init__(self) -> None:
        self.stopped = False

    def process_file_batch(self, batch, _skip_existing, _check_modifications):
        return SimpleNamespace(
            files_processed=len(batch),
            files_added=len(batch),
            files_updated=0,
            files_skipped=0,
            files_failed=0,
            added_tracks=[],
            # #4841: the scanner now carries per-file failures up from each
            # batch, so a double standing in for ScanResult has to model it.
            failures=[],
        )

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture
def music_dir(tmp_path):
    """20 fake audio files — enough for several batches at batch_size=5."""
    root = tmp_path / "music"
    root.mkdir()
    for i in range(20):
        (root / f"track_{i:02d}.mp3").write_bytes(b"\x00")
    return root


def _run_scan(directory, batch_size=5):
    """Drive a real LibraryScanner and return every progress frame it emits."""
    scanner = LibraryScanner(library_database=object())
    scanner.batch_processor = _StubBatchProcessor()

    frames: list[dict] = []
    scanner.set_progress_callback(frames.append)
    scanner.scan_directories(
        [str(directory)], recursive=True, skip_existing=False,
        check_modifications=False, batch_size=batch_size,
    )
    return frames


class TestScannerEmitsARealFraction:
    def test_processing_frames_carry_a_progress_fraction(self, music_dir):
        frames = _run_scan(music_dir)
        processing = [f for f in frames if f.get('stage') == 'processing']

        assert processing, "expected at least one processing frame"
        assert all('progress' in f for f in processing), (
            "every processing frame must carry a `progress` fraction — without it "
            "scan_progress_percentage() is structurally always None (#4616)"
        )
        assert all(0.0 <= f['progress'] <= 1.0 for f in processing)

    def test_percentage_is_neither_always_null_nor_pinned_at_100(self, music_dir):
        frames = _run_scan(music_dir)
        percentages = [
            scan_progress_percentage(f) for f in frames if f.get('stage') == 'processing'
        ]

        # Fails on current-master behaviour (all None).
        assert all(p is not None for p in percentages), (
            f"percentage must be a number during processing, got {percentages}"
        )
        # Fails on the pre-#4411 behaviour (processed/files_found ≈ 100% always).
        assert any(0 < p < 100 for p in percentages), (
            f"percentage must move through the middle of the range, got {percentages}"
        )
        assert percentages[0] < 100, (
            f"first processing frame must not be pinned at ~100% (#4411), got {percentages[0]}"
        )
        assert percentages[-1] == 100

    def test_percentage_is_monotonically_non_decreasing(self, music_dir):
        frames = _run_scan(music_dir)
        percentages = [
            scan_progress_percentage(f)
            for f in frames
            if scan_progress_percentage(f) is not None
        ]
        assert percentages == sorted(percentages), (
            f"progress must never go backwards, got {percentages}"
        )

    def test_denominator_is_the_pre_count_not_the_running_tally(self, music_dir):
        """#4411 guard: `total_expected` is fixed; `total_found` climbs."""
        frames = _run_scan(music_dir)
        processing = [f for f in frames if f.get('stage') == 'processing']

        expected = {f['total_expected'] for f in processing}
        assert expected == {20}, f"denominator must be the fixed pre-count, got {expected}"

        found = [f['total_found'] for f in processing]
        assert found[0] < found[-1], (
            "sanity check: total_found is the running tally that must NOT be used "
            f"as a denominator, got {found}"
        )

    def test_empty_directory_stays_indeterminate(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        frames = _run_scan(empty)
        assert all(scan_progress_percentage(f) is None for f in frames), (
            "a zero total must stay indeterminate rather than divide by zero"
        )


class TestBothBridgesSeeTheSameNumbers:
    """Manual router and auto-scanner share `scan_progress_percentage`, and both
    must prefer the pre-counted total over the running discovery tally."""

    @staticmethod
    def _bridge_total(data):
        # The identical expression used by routers/library_scan.py and
        # services/library_auto_scanner.py.
        return (
            data.get('total_expected')
            or data.get('total_found', 0)
            or data.get('processed', 0)
        )

    def test_bridges_report_the_pre_counted_total(self, music_dir):
        frames = [f for f in _run_scan(music_dir) if f.get('stage') == 'processing']
        totals = {self._bridge_total(f) for f in frames}
        assert totals == {20}, f"both bridges must report the fixed total, got {totals}"

    def test_bridge_total_falls_back_when_no_pre_count(self):
        """Payloads without `total_expected` keep the previous behaviour."""
        assert self._bridge_total({'total_found': 7, 'processed': 3}) == 7
        assert self._bridge_total({'processed': 3}) == 3
        assert self._bridge_total({}) == 0

    def test_both_bridge_modules_use_total_expected(self):
        """Guards against one emitter being updated and the other forgotten."""
        backend = Path(_BACKEND)
        for rel in ("routers/library_scan.py", "services/library_auto_scanner.py"):
            source = (backend / rel).read_text()
            assert "total_expected" in source, f"{rel} must prefer the pre-counted total (#4616)"


class TestFileDiscoveryCount:
    def test_count_matches_what_discovery_yields(self, music_dir):
        from auralis.library.scanner.file_discovery import FileDiscovery

        discovery = FileDiscovery()
        counted = discovery.count_audio_files(str(music_dir), recursive=True)
        yielded = len(list(discovery.discover_audio_files(str(music_dir), recursive=True)))
        assert counted == yielded == 20

    def test_count_ignores_non_audio_files(self, tmp_path):
        from auralis.library.scanner.file_discovery import FileDiscovery

        root = tmp_path / "mixed"
        root.mkdir()
        (root / "song.mp3").write_bytes(b"\x00")
        (root / "cover.jpg").write_bytes(b"\x00")
        (root / "notes.txt").write_text("x")

        assert FileDiscovery().count_audio_files(str(root), recursive=True) == 1

"""
Regression tests for FingerprintGenerator event-loop offloading (#3854)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

get_or_generate is async but previously ran sync work on the event loop:
the fingerprint DB read/write and the full-file audio decode. On stream
startup that added to first-chunk latency; in the background queue drain it
accumulated 10-30 s of stalls across 50 tracks. The fix wraps each sync step
in asyncio.to_thread, so the loop stays responsive.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import sys
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import analysis.fingerprint_generator as fpg
from analysis.fingerprint_generator import FingerprintGenerator


def _make_generator(get_by_track_id):
    """Build a FingerprintGenerator whose fingerprints repo uses the given
    get_by_track_id callable."""
    repo = Mock()
    repo.get_by_track_id = get_by_track_id
    factory = Mock()
    factory.fingerprints = repo
    return FingerprintGenerator(session_factory=Mock(), get_repository_factory=lambda: factory)


class TestDbLookupOffload:
    @pytest.mark.asyncio
    async def test_db_lookup_runs_off_event_loop_thread(self):
        """The cache-hit DB read happens on a worker thread (to_thread)."""
        main_thread = threading.current_thread()
        seen: list[threading.Thread] = []

        def _lookup(track_id):
            seen.append(threading.current_thread())
            rec = Mock()
            rec.lufs = -14.0  # a real value so _record_to_dict yields data
            return rec

        gen = _make_generator(_lookup)
        result = await gen.get_or_generate(track_id=1, filepath="/fake.wav")

        assert seen, "get_by_track_id was called"
        assert seen[0] is not main_thread, (
            "DB lookup must run via asyncio.to_thread, not on the event-loop thread"
        )
        assert result is not None  # cache hit returned a dict

    @pytest.mark.asyncio
    async def test_event_loop_responsive_during_slow_db_lookup(self):
        """A concurrent ticker keeps advancing while a slow DB read runs."""

        def _slow_lookup(track_id):
            time.sleep(0.3)  # blocking, like a slow sync DB call
            rec = Mock()
            rec.lufs = -14.0
            return rec

        gen = _make_generator(_slow_lookup)

        ticks = 0

        async def _ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        ticker = asyncio.create_task(_ticker())
        try:
            await gen.get_or_generate(track_id=1, filepath="/fake.wav")
        finally:
            ticker.cancel()
            try:
                await ticker
            except asyncio.CancelledError:
                pass

        assert ticks >= 10, (
            f"Event loop appeared blocked during DB lookup (only {ticks} ticks); "
            "the sync read is likely running on the event-loop thread"
        )


class TestWindowedComputeOffload:
    """#5531: the heavy sync work in _generate_via_rust is now one bounded
    windowed-pipeline task on the executor (decode + Rust analysis), instead
    of a full-file load followed by a raw schema call."""

    def test_executor_task_delegates_to_the_windowed_pipeline(self, monkeypatch):
        """_compute_windowed_fingerprint_in_thread runs the shared windowed
        pipeline and returns its result verbatim."""
        expected = {"lufs": -14.0, "bass_pct": 0.2}
        recorded: list[Path] = []

        def _fake_windowed(_analyzer, path):
            recorded.append(path)
            return expected

        import auralis.analysis.fingerprint.windowed_compute as wc

        monkeypatch.setattr(wc, "compute_windowed_fingerprint", _fake_windowed)

        result = fpg._compute_windowed_fingerprint_in_thread("/fake.wav")

        assert result is expected
        assert recorded and recorded[0] == Path("/fake.wav")

    def test_executor_task_returns_none_when_the_pipeline_fails(self, monkeypatch):
        import auralis.analysis.fingerprint.windowed_compute as wc

        def _boom(_analyzer, _path):
            raise RuntimeError("decode failed")

        monkeypatch.setattr(wc, "compute_windowed_fingerprint", _boom)

        assert fpg._compute_windowed_fingerprint_in_thread("/fake.wav") is None

    @pytest.mark.asyncio
    async def test_fingerprint_compute_runs_off_thread(self):
        """_generate_via_rust runs the compute on an executor worker, not the
        event loop."""
        main_thread = threading.current_thread()
        seen: list[threading.Thread] = []

        def _fake_compute(_filepath):
            seen.append(threading.current_thread())
            return {"lufs": -14.0}

        gen = FingerprintGenerator(session_factory=Mock(), get_repository_factory=Mock())

        orig = fpg._compute_windowed_fingerprint_in_thread
        fpg._compute_windowed_fingerprint_in_thread = _fake_compute
        try:
            result = await gen._generate_via_rust(filepath="/fake.wav", track_id=1)
        finally:
            fpg._compute_windowed_fingerprint_in_thread = orig

        assert result == {"lufs": -14.0}
        assert seen, "the windowed compute was called"
        assert seen[0] is not main_thread, (
            "the fingerprint compute must run on an executor worker, not the event-loop thread"
        )

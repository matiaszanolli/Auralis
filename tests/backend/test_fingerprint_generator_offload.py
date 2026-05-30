"""
Regression tests for FingerprintGenerator event-loop offloading (#3854)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

get_or_generate is async but previously ran sync work on the event loop:
the fingerprint DB read/write and the full-file audio decode. On stream
startup that added to first-chunk latency; in the background queue drain it
accumulated 10-30 s of stalls across 50 tracks. The fix wraps each sync step
in asyncio.to_thread, so the loop stays responsive.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import sys
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import analysis.fingerprint_generator as fpg
from analysis.fingerprint_generator import FingerprintGenerator, _load_and_prepare_audio


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


class TestLoadAndPrepareAudio:
    def test_helper_interleaves_stereo_as_float32(self):
        """_load_and_prepare_audio interleaves stereo and casts to float32."""
        stereo = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)  # (frames, ch)

        def _fake_load(_fp):
            return stereo, 48000

        orig = fpg.load_audio
        fpg.load_audio = _fake_load
        try:
            arr, sr, ch = _load_and_prepare_audio("/fake.wav")
        finally:
            fpg.load_audio = orig

        assert ch == 2
        assert sr == 48000
        assert arr.dtype == np.float32
        # Fortran flatten interleaves: L1,L2,R1,R2 -> column-major of (frames,ch)
        assert np.allclose(arr, np.array([1.0, 3.0, 2.0, 4.0], dtype=np.float32))

    @pytest.mark.asyncio
    async def test_audio_load_runs_off_thread(self):
        """_generate_via_rust loads audio on a worker thread, not the loop."""
        main_thread = threading.current_thread()
        seen: list[threading.Thread] = []

        def _fake_load(_fp):
            seen.append(threading.current_thread())
            return np.zeros((1000, 2), dtype=np.float32), 44100

        gen = FingerprintGenerator(session_factory=Mock(), get_repository_factory=Mock())

        orig = fpg.load_audio
        fpg.load_audio = _fake_load
        try:
            # Returns None without a real Rust module — we only assert the
            # audio load ran off the event-loop thread.
            await gen._generate_via_rust(filepath="/fake.wav", track_id=1)
        finally:
            fpg.load_audio = orig

        assert seen, "load_audio was called"
        assert seen[0] is not main_thread, (
            "load_audio must run via asyncio.to_thread, not on the event-loop thread"
        )

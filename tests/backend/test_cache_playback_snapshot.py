"""
Regression tests: _process_priorities uses one consistent playback snapshot (#4546)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`StreamlinedCacheWorker._process_priorities` read four independent pieces of
cache-manager state (`current_track_id`, the chunk derived from
`current_position`, `current_preset`, `intensity`) as four separate
unsynchronised reads, then awaited a DB round-trip before using them together.
A track or preset change landing between any two reads produced a mismatched
tuple driving chunk processing — e.g. track A's id with track B's position,
giving a chunk index past A's end.

`StreamlinedCacheManager.get_playback_snapshot()` now returns all of it from
one `_lock` acquisition, mirroring `AudioFileManager.get_state_snapshot()`
(#3474), and the worker re-validates the track id after the await.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from cache.manager import PlaybackSnapshot, StreamlinedCacheManager
from core.streamlined_worker import StreamlinedCacheWorker


class TestGetPlaybackSnapshot:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_track(self):
        mgr = StreamlinedCacheManager()
        assert await mgr.get_playback_snapshot() is None

    @pytest.mark.asyncio
    async def test_returns_all_fields_from_one_generation(self):
        mgr = StreamlinedCacheManager()
        await mgr.update_position(
            track_id=7, position=35.0, preset="warm", intensity=0.8, track_duration=120.0
        )

        snap = await mgr.get_playback_snapshot()

        assert snap is not None
        assert snap.track_id == 7
        assert snap.position == 35.0
        assert snap.preset == "warm"
        assert snap.intensity == 0.8
        # chunk derived from the snapshotted position, not a fresh read
        assert snap.chunk_idx == mgr._get_current_chunk(35.0)

    @pytest.mark.asyncio
    async def test_snapshot_is_serialised_against_update_position(self):
        """A writer flipping every field must never be observed half-applied."""
        mgr = StreamlinedCacheManager()
        await mgr.update_position(
            track_id=1, position=0.0, preset="adaptive", intensity=1.0, track_duration=600.0
        )

        # Two fully-consistent generations; any mix of the two is a torn read.
        generations = {
            1: ("adaptive", 1.0, 0.0),
            2: ("warm", 0.5, 400.0),
        }
        errors: list[str] = []
        stop = asyncio.Event()

        async def writer():
            gen = 1
            while not stop.is_set():
                gen = 2 if gen == 1 else 1
                preset, intensity, position = generations[gen]
                await mgr.update_position(
                    track_id=gen,
                    position=position,
                    preset=preset,
                    intensity=intensity,
                    track_duration=600.0,
                )
                await asyncio.sleep(0)

        async def reader():
            for _ in range(400):
                snap = await mgr.get_playback_snapshot()
                if snap is None:
                    continue
                expected = generations.get(snap.track_id)
                if expected is None:
                    errors.append(f"unknown generation {snap.track_id}")
                    return
                preset, intensity, position = expected
                if (snap.preset, snap.intensity, snap.position) != (preset, intensity, position):
                    errors.append(f"torn snapshot: {snap}")
                    return
                await asyncio.sleep(0)

        w = asyncio.create_task(writer())
        await asyncio.gather(*[reader() for _ in range(3)])
        stop.set()
        await w

        assert not errors, errors[:3]


def _make_worker(cache_manager, track=Mock()):
    library_database = Mock()
    library_database.tracks.get_by_id = Mock(return_value=track)
    return StreamlinedCacheWorker(
        cache_manager=cache_manager,
        library_database=library_database,
    )


class TestProcessPrioritiesUsesSnapshot:
    @pytest.mark.asyncio
    async def test_uses_snapshot_values_not_live_reads(self, monkeypatch):
        """Values passed downstream must come from the snapshot, even if the
        manager's live fields change during the awaited DB call."""
        mgr = StreamlinedCacheManager()
        await mgr.update_position(
            track_id=1, position=5.0, preset="warm", intensity=0.8, track_duration=600.0
        )

        worker = _make_worker(mgr)

        # Mutate the live fields the moment the DB call is made — the old code
        # would have read some of these; the snapshot must be immune.
        def _get_by_id(_track_id):
            mgr.current_preset = "bright"
            mgr.intensity = 0.1
            mgr.current_position = 500.0
            return Mock()

        worker.library_database.tracks.get_by_id = _get_by_id

        # Tier 1 gets current_chunk + 1, Tier 2 gets current_chunk — capture
        # them separately so one does not overwrite the other.
        tier1: dict = {}
        tier2: dict = {}

        async def _capture_tier1(track, track_id, chunk_idx, preset, intensity):
            tier1.update(
                track_id=track_id, chunk_idx=chunk_idx, preset=preset, intensity=intensity
            )

        async def _capture_tier2(track, track_id, chunk_idx, preset, intensity):
            tier2.update(
                track_id=track_id, chunk_idx=chunk_idx, preset=preset, intensity=intensity
            )

        monkeypatch.setattr(worker, "_ensure_tier1_chunk", _capture_tier1)
        monkeypatch.setattr(worker, "_build_tier2_cache", _capture_tier2)

        await worker._process_priorities()

        assert tier1["preset"] == "warm", "preset must come from the snapshot"
        assert tier1["intensity"] == 0.8, "intensity must come from the snapshot"
        assert tier1["chunk_idx"] == mgr._get_current_chunk(5.0) + 1
        # Tier 2 must see the same generation, derived from the same position.
        assert tier2["chunk_idx"] == mgr._get_current_chunk(5.0)
        assert (tier2["preset"], tier2["intensity"]) == ("warm", 0.8)

    @pytest.mark.asyncio
    async def test_bails_when_track_changes_during_db_call(self, monkeypatch):
        """A track change mid-await must abandon the tick, not cache chunks
        under the previous track's id."""
        mgr = StreamlinedCacheManager()
        await mgr.update_position(
            track_id=1, position=5.0, preset="adaptive", intensity=1.0, track_duration=600.0
        )

        worker = _make_worker(mgr)

        def _get_by_id(_track_id):
            mgr.current_track_id = 99  # playback moved on
            return Mock()

        worker.library_database.tracks.get_by_id = _get_by_id

        called: list[str] = []

        async def _tier1(*args, **kwargs):
            called.append("tier1")

        async def _tier2(*args, **kwargs):
            called.append("tier2")

        monkeypatch.setattr(worker, "_ensure_tier1_chunk", _tier1)
        monkeypatch.setattr(worker, "_build_tier2_cache", _tier2)

        await worker._process_priorities()

        assert called == [], (
            "worker cached chunks for track 1 after playback moved to 99 (#4546)"
        )

    @pytest.mark.asyncio
    async def test_no_track_playing_returns_early(self, monkeypatch):
        mgr = StreamlinedCacheManager()
        worker = _make_worker(mgr)

        called: list[str] = []
        monkeypatch.setattr(
            worker, "_ensure_tier1_chunk", lambda *a, **k: called.append("tier1")
        )

        await worker._process_priorities()
        assert called == []

    def test_worker_reads_only_through_the_snapshot(self):
        """WIRING guard: the four fields must not be read directly again."""
        import inspect

        source = inspect.getsource(StreamlinedCacheWorker._process_priorities)
        assert "get_playback_snapshot" in source
        # The only permitted direct read is the post-await re-validation.
        assert source.count("cache_manager.current_preset") == 0
        assert source.count("cache_manager.intensity") == 0
        assert source.count("cache_manager.current_position") == 0


def test_snapshot_is_a_named_tuple():
    """Consumers unpack by attribute; keep the shape stable."""
    snap = PlaybackSnapshot(
        track_id=1, position=2.0, chunk_idx=0, preset="adaptive", intensity=1.0
    )
    assert snap.track_id == 1
    assert tuple(snap) == (1, 2.0, 0, "adaptive", 1.0)

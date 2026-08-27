"""Enhanced-path seek lands on the requested source time (#4557).

The seek math computed ``int(position / CHUNK_INTERVAL)`` and trimmed
``position - index * CHUNK_INTERVAL`` off the front of the delivered buffer.
That maps onto the chunk *core* timeline — but the buffer it trims has already
had ``OVERLAP_DURATION`` removed by ``ChunkOperations.extract_chunk_segment``,
because the previous chunk emitted that audio. So every enhanced seek to a
position >= CHUNK_INTERVAL started exactly OVERLAP_DURATION past the requested
point, and the transport read 5s ahead of the audio for the rest of the stream.

The emitted timeline is::

    chunk 0 -> [0, 15)     (CHUNK_DURATION, nothing skipped)
    chunk 1 -> [15, 25)    (1*10 + 5)
    chunk 2 -> [25, 35)    (2*10 + 5)

Contiguous, but offset by OVERLAP_DURATION from the core timeline for every
chunk after the first.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import sys
from pathlib import Path

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.chunk_boundaries import (  # noqa: E402
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    OVERLAP_DURATION,
    SEEK_MIN_CHUNK_REMAINDER,
    chunk_for_position,
    emitted_chunk_length,
    emitted_chunk_start,
)

# Plenty of chunks so the min-remainder advance never hits the last-chunk clamp.
TOTAL_CHUNKS = 50


class TestEmittedChunkStart:
    """The emitted timeline is the core timeline shifted by OVERLAP_DURATION,
    except for chunk 0."""

    def test_chunk_zero_starts_at_zero(self):
        assert emitted_chunk_start(0) == 0.0

    @pytest.mark.parametrize("idx,expected", [(1, 15.0), (2, 25.0), (3, 35.0), (10, 105.0)])
    def test_later_chunks_include_the_overlap_skip(self, idx, expected):
        assert emitted_chunk_start(idx) == expected
        # Explicitly: core start + the overlap the extractor skips.
        assert emitted_chunk_start(idx) == idx * CHUNK_INTERVAL + OVERLAP_DURATION

    def test_emitted_ranges_are_contiguous(self):
        """No gaps and no overlap in what the client actually receives."""
        for idx in range(0, 20):
            end = emitted_chunk_start(idx) + emitted_chunk_length(idx)
            assert end == pytest.approx(emitted_chunk_start(idx + 1)), (
                f"gap or overlap between chunk {idx} and {idx + 1}"
            )


class TestChunkForPosition:
    """The issue's test plan: hand-computed expectations under
    CHUNK_DURATION=15 / CHUNK_INTERVAL=10 / OVERLAP_DURATION=5."""

    @pytest.mark.parametrize(
        "position,expected_idx,expected_offset",
        [
            (0.0, 0, 0.0),     # start of track
            (5.0, 0, 5.0),     # still inside chunk 0's 15s emission
            (12.0, 0, 12.0),   # chunk 0 emits up to 15s — NOT chunk 1
            (15.0, 1, 0.0),    # exactly the chunk 1 boundary
            (27.0, 2, 2.0),    # chunk 2 emits [25, 35)
            (33.0, 2, 8.0),
        ],
    )
    def test_maps_position_to_the_chunk_that_emits_it(
        self, position, expected_idx, expected_offset
    ):
        idx, offset, effective = chunk_for_position(position, TOTAL_CHUNKS)
        assert idx == expected_idx
        assert offset == pytest.approx(expected_offset)
        assert effective == pytest.approx(position)

    @pytest.mark.parametrize("position", [0.0, 5.0, 12.0, 15.0, 27.0, 33.0, 100.0, 247.5])
    def test_offset_reconstructs_the_requested_source_time(self, position):
        """The defining property: emitted_start + offset == the request."""
        idx, offset, effective = chunk_for_position(position, TOTAL_CHUNKS)
        assert emitted_chunk_start(idx) + offset == pytest.approx(effective)

    @pytest.mark.parametrize("position", [12.0, 27.0, 33.0, 100.0])
    def test_does_not_land_overlap_seconds_late(self, position):
        """The regression itself: the old math produced position + 5."""
        idx, offset, _ = chunk_for_position(position, TOTAL_CHUNKS)
        landed = emitted_chunk_start(idx) + offset
        assert landed != pytest.approx(position + OVERLAP_DURATION)
        assert landed == pytest.approx(position)

    def test_chunk_zero_case_is_unchanged(self):
        """Regression guard from the issue: P < OVERLAP_DURATION must still
        map to chunk 0 with offset == P."""
        for position in (0.0, 1.0, 2.5, 4.9):
            idx, offset, effective = chunk_for_position(position, TOTAL_CHUNKS)
            assert idx == 0
            assert offset == pytest.approx(position)
            assert effective == pytest.approx(position)

    def test_negative_position_clamps_to_zero(self):
        assert chunk_for_position(-5.0, TOTAL_CHUNKS) == (0, 0.0, 0.0)

    def test_position_past_the_end_clamps_to_the_last_chunk(self):
        idx, _, _ = chunk_for_position(10_000.0, TOTAL_CHUNKS)
        assert idx == TOTAL_CHUNKS - 1

    def test_position_past_duration_retains_audible_last_chunk_audio(self):
        duration = 60.0
        total_chunks = 6

        idx, offset, effective = chunk_for_position(
            duration + 5.0,
            total_chunks,
            total_duration=duration,
        )

        assert idx == total_chunks - 1
        assert effective == pytest.approx(duration - SEEK_MIN_CHUNK_REMAINDER)
        assert offset == pytest.approx(4.5)
        assert duration - effective == pytest.approx(SEEK_MIN_CHUNK_REMAINDER)


class TestSliverAvoidance:
    """A seek must not deliver a first chunk trimmed down to nothing."""

    @pytest.mark.parametrize("position", [14.9, 24.95, 34.99])
    def test_advances_when_the_remainder_would_be_a_sliver(self, position):
        idx, offset, effective = chunk_for_position(position, TOTAL_CHUNKS)

        assert offset == 0.0, "advanced seeks start at a chunk boundary"
        assert effective == emitted_chunk_start(idx)
        # Never advances backwards, and never by more than the sliver.
        assert effective >= position
        assert effective - position < SEEK_MIN_CHUNK_REMAINDER

    @pytest.mark.parametrize("position", [0.0, 5.0, 12.0, 27.0, 33.0])
    def test_does_not_advance_when_the_remainder_is_healthy(self, position):
        _, _, effective = chunk_for_position(position, TOTAL_CHUNKS)
        assert effective == pytest.approx(position)

    def test_every_first_chunk_retains_at_least_the_floor(self):
        """Sweep the emitted timeline: no seek yields a sub-floor first chunk."""
        position = 0.0
        while position < 200.0:
            idx, offset, _ = chunk_for_position(position, TOTAL_CHUNKS)
            remaining = emitted_chunk_length(idx) - offset
            assert remaining >= SEEK_MIN_CHUNK_REMAINDER - 1e-9, (
                f"seek to {position}s left only {remaining}s of chunk {idx}"
            )
            position += 0.1

    def test_last_chunk_is_never_advanced_past(self):
        """The clamp wins over the sliver rule — there is nowhere to advance."""
        total = 3
        # A position deep inside the final chunk's emission.
        position = emitted_chunk_start(total - 1) + CHUNK_INTERVAL - 0.01
        idx, _, _ = chunk_for_position(position, total)
        assert idx == total - 1


class TestCacheManagerCurrentChunkMatchesChunkForPosition:
    """#4791: StreamlinedCacheManager._get_current_chunk used to derive the
    chunk index via the naive core-timeline ``position // CHUNK_INTERVAL``,
    disagreeing with chunk_for_position() (what stream_seek.py already used,
    #4557) for roughly the first half of every emitted chunk window. This
    fed PlaybackSnapshot.chunk_idx (Tier-1 warming / add_chunk's tier
    auto-detect), so the "hot" cache tier was one chunk ahead of the live
    position for those windows.
    """

    @staticmethod
    def _make_manager(total_chunks: int):
        import sys
        if _BACKEND not in sys.path:
            sys.path.insert(0, _BACKEND)
        from cache.manager import StreamlinedCacheManager, TrackCacheStatus

        manager = StreamlinedCacheManager()
        manager.current_track_id = 1
        manager.track_status[1] = TrackCacheStatus(track_id=1, total_chunks=total_chunks)
        return manager

    # Kept clear of [24.5, 25) — inside SEEK_MIN_CHUNK_REMAINDER of chunk 1's
    # end, where chunk_for_position's sliver-avoidance rule legitimately
    # advances to chunk 2 (tested separately in TestSliverAvoidance above).
    @pytest.mark.parametrize("position", [20.0, 21.0, 23.0, 24.4])
    def test_first_half_of_chunk_1_window(self, position):
        """p in [20,25) must map to chunk 1, not the naive chunk 2."""
        manager = self._make_manager(TOTAL_CHUNKS)
        expected = chunk_for_position(position, TOTAL_CHUNKS)[0]
        assert manager._get_current_chunk(position) == expected == 1

    @pytest.mark.parametrize("position", [30.0, 31.0, 33.0, 34.4])
    def test_first_half_of_chunk_2_window(self, position):
        """p in [30,35) must map to chunk 2, not the naive chunk 3."""
        manager = self._make_manager(TOTAL_CHUNKS)
        expected = chunk_for_position(position, TOTAL_CHUNKS)[0]
        assert manager._get_current_chunk(position) == expected == 2

    def test_matches_chunk_for_position_across_a_full_sweep(self):
        manager = self._make_manager(TOTAL_CHUNKS)
        position = 0.0
        while position < emitted_chunk_start(TOTAL_CHUNKS - 1):
            expected = chunk_for_position(position, TOTAL_CHUNKS)[0]
            assert manager._get_current_chunk(position) == expected, (
                f"mismatch at position={position}"
            )
            position += 0.3


class TestSeekMathUsesSharedConstants:
    """CONSISTENCY: the seek derivation and the extraction must be provably
    sourced from the same constants."""

    def test_stream_seek_imports_the_helper(self):
        source = (Path(_BACKEND) / "core" / "stream_seek.py").read_text()
        assert "chunk_for_position" in source, (
            "stream_seek must derive the chunk from the emitted timeline (#4557)"
        )
        # The old core-timeline derivation must be gone. Checked against code
        # only — the string appears legitimately in the explanatory comment.
        code = "\n".join(
            line for line in source.split("\n") if not line.lstrip().startswith("#")
        )
        assert "int(start_position / chunk_interval)" not in code

    def test_recovery_positions_use_the_emitted_start(self):
        """A recovery position on the core timeline replays OVERLAP_DURATION of
        already-delivered audio."""
        # #5032 moved each handler's per-chunk loop into a companion pump
        # module, and the recovery positions are computed inside that loop —
        # so the guard follows them there. The handlers themselves no longer
        # compute a recovery position at all.
        for module in ("stream_seek_chunks.py", "stream_enhanced_chunks.py"):
            source = (Path(_BACKEND) / "core" / module).read_text()
            assert "emitted_chunk_start" in source, (
                f"{module} must compute recovery positions from the emitted "
                "timeline (#4557)"
            )

    def test_constants_are_self_consistent(self):
        assert CHUNK_INTERVAL == CHUNK_DURATION - OVERLAP_DURATION

    @pytest.mark.parametrize("module_path", [
        "cache/manager.py",
        "routers/enhancement.py",
    ])
    def test_position_to_chunk_derivations_use_chunk_for_position(self, module_path):
        """#4791: cache/manager.py's _get_current_chunk and routers/
        enhancement.py's pre-fetch chunk index used to derive the chunk
        index via the naive core-timeline
        ``position // CHUNK_INTERVAL``/``position / CHUNK_INTERVAL`` —
        off by one for roughly the first half of every emitted chunk
        window, same root cause #4557 fixed in stream_seek.py. Extends
        test_stream_seek_imports_the_helper's guard to these two files.

        Checks for the exact prior expressions rather than banning the
        ``CHUNK_INTERVAL`` substring generally — both files legitimately
        reference it elsewhere (re-exports, an unrelated total-chunk-COUNT
        formula in a #4124 docstring), same rationale as
        test_stream_seek_imports_the_helper's own "checked against code
        only" note.
        """
        source = (Path(_BACKEND) / module_path).read_text()
        assert "chunk_for_position" in source, (
            f"{module_path} must derive the chunk index from the emitted "
            "timeline via chunk_for_position() (#4557/#4791)"
        )
        for forbidden in (
            "position // CHUNK_INTERVAL",
            "position / CHUNK_INTERVAL",
            "current_time / CHUNK_INTERVAL",
            "current_time // CHUNK_INTERVAL",
        ):
            assert forbidden not in source, (
                f"{module_path} still contains the naive core-timeline "
                f"position -> chunk derivation ({forbidden!r}) (#4791)"
            )

"""
Streamlined Cache Playback Position
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tracks the current track, position, preset and intensity for
StreamlinedCacheManager, and maps positions onto chunk indices. Split out of
cache/manager.py (#5238).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging

from core.chunk_boundaries import chunk_for_position, content_chunk_count

from .eviction_mixin import CacheEvictionMixin
from .models import PlaybackSnapshot, TrackCacheStatus

logger = logging.getLogger(__name__)


class CachePlaybackMixin(CacheEvictionMixin):
    """Playback-position state and position-to-chunk mapping.

    State is initialized by StreamlinedCacheManager.__init__, not here —
    declared here only so type checkers know this mixin depends on it.
    """

    current_position: float
    current_preset: str
    intensity: float
    _lock: asyncio.Lock

    def _get_current_chunk(self, position: float) -> int:
        """Calculate chunk index from playback position.

        Uses chunk_for_position() (#4557/#4791) — the mapping onto the chunk
        that actually EMITS this position, not the naive core-timeline
        floor-division by CHUNK_INTERVAL, which is off by one for roughly
        the first half of every emitted chunk window (every chunk after the
        first is offset by OVERLAP_DURATION from the core timeline; see
        chunk_boundaries.emitted_chunk_start).
        """
        total_chunks = 1
        status = self.track_status.get(self.current_track_id) if self.current_track_id else None
        if status is not None:
            total_chunks = status.total_chunks
        return chunk_for_position(
            position,
            total_chunks,
            total_duration=status.total_duration if status is not None else None,
        )[0]

    def _calculate_total_chunks(self, duration: float) -> int:
        """Content-carrying chunk count — delegates to the chunk-model SoT.

        The cache-completion target must equal ``ChunkedAudioProcessor.
        total_chunks``, which is itself set from ``content_chunk_count()``, so
        this delegates rather than re-deriving the formula (#4620). The naive
        ``ceil(duration / CHUNK_INTERVAL)`` over-counted a 0-content trailing
        chunk for durations in ``(n*INTERVAL, n*INTERVAL + OVERLAP)`` (#4124);
        that fix now lives in exactly one place.
        """
        return content_chunk_count(duration)

    async def get_playback_snapshot(self) -> "PlaybackSnapshot | None":
        """Read the four playback fields in one critical section (#4546).

        ``update_position`` writes ``current_track_id``, ``current_position``,
        ``current_preset`` and ``intensity`` together under ``_lock``. Readers
        that fetch them as four separate awaited/unsynchronised reads can
        observe a mix of generations — e.g. track A's id paired with track B's
        position, yielding a chunk index past A's end. Mirrors
        ``AudioFileManager.get_state_snapshot()`` (#3474), which exists for
        exactly this hazard on the player side.

        Returns ``None`` when no track is playing, preserving the
        ``if not current_track_id: return`` guard callers had before.
        """
        async with self._lock:
            if not self.current_track_id:
                return None
            return PlaybackSnapshot(
                track_id=self.current_track_id,
                position=self.current_position,
                chunk_idx=self._get_current_chunk(self.current_position),
                preset=self.current_preset,
                intensity=self.intensity,
            )

    async def update_position(
        self,
        track_id: int,
        position: float,
        preset: str = "adaptive",
        intensity: float = 1.0,
        track_duration: float | None = None
    ) -> None:
        """
        Update current playback position.

        Args:
            track_id: Current track ID
            position: Position in seconds
            preset: Current preset
            intensity: Processing intensity
            track_duration: Total track duration (for cache planning)
        """
        async with self._lock:
            track_changed = track_id != self.current_track_id
            preset_changed = preset != self.current_preset
            # Captured before the write so the change log below reports the
            # real transition; it previously read the already-updated fields
            # and always printed "X -> X".
            previous_track_id = self.current_track_id
            previous_preset = self.current_preset

            # Update state
            self.current_track_id = track_id
            self.current_position = position
            self.current_preset = preset
            self.intensity = intensity

            # Initialize track status if new track
            if track_changed and track_duration:
                total_chunks = self._calculate_total_chunks(track_duration)
                self.track_status[track_id] = TrackCacheStatus(
                    track_id=track_id,
                    total_chunks=total_chunks,
                    total_duration=track_duration,
                )
                logger.info(f"Track {track_id}: {total_chunks} chunks needed ({track_duration:.1f}s)")

            # Clear old Tier 1 cache on track change
            if track_changed:
                await self._clear_tier1_cache()
                logger.info(f"Track changed: {previous_track_id} -> {track_id}, cleared Tier 1")

            # Clear old Tier 2 cache on preset change (need to recache processed chunks)
            if preset_changed and track_id in self.track_status:
                await self._clear_tier2_processed_chunks(track_id)
                logger.info(f"Preset changed: {previous_preset} -> {preset}, cleared processed chunks")

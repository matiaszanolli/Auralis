"""
Multi-Tier Buffer Manager for Auralis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CPU-inspired hierarchical caching with branch prediction for audio chunks.

Architecture:
- L1 Cache (Hot): Current + next chunk for high-probability presets (0ms latency)
- L2 Cache (Warm): Branch scenarios for predicted preset switches (100-200ms latency)
- L3 Cache (Cold): Long-term section cache for current preset (500ms-2s latency)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import time
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Cache configuration
CHUNK_DURATION = 30  # seconds
AVAILABLE_PRESETS = ["adaptive", "gentle", "warm", "bright", "punchy"]

# Memory limits per tier (MB)
L1_MAX_SIZE_MB = 18
L2_MAX_SIZE_MB = 36
L3_MAX_SIZE_MB = 45
TOTAL_MAX_SIZE_MB = 99

# Chunk size estimate (stereo 44.1kHz, 30s, float32)
CHUNK_SIZE_MB = 3.0


@dataclass
class CacheEntry:
    """Represents a cached chunk."""
    track_id: int
    preset: str
    chunk_idx: int
    intensity: float
    timestamp: float  # When cached
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    probability: float = 1.0  # Prediction probability (for L2/L3)

    def key(self) -> str:
        """Generate unique key for this entry."""
        return f"{self.track_id}_{self.preset}_{self.intensity:.1f}_{self.chunk_idx}"

    def size_mb(self) -> float:
        """Estimated size in MB."""
        return CHUNK_SIZE_MB


@dataclass
class BranchScenario:
    """Represents a predicted future scenario."""
    name: str  # e.g., "switch_to_punchy", "seek_forward"
    preset: str
    chunk_range: range
    probability: float
    created_at: float = field(default_factory=time.time)


class CacheTier:
    """
    Represents a single cache tier (L1, L2, or L3).
    """

    def __init__(self, name: str, max_size_mb: float):
        self.name = name
        self.max_size_mb = max_size_mb
        self.entries: Dict[str, CacheEntry] = {}  # key -> CacheEntry
        self._lock = asyncio.Lock()

    def get_size_mb(self) -> float:
        """Calculate current cache size in MB."""
        return sum(entry.size_mb() for entry in self.entries.values())

    async def get_entry(self, key: str) -> Optional[CacheEntry]:
        """Get entry and update access stats (with locking)."""
        async with self._lock:
            if key in self.entries:
                entry = self.entries[key]
                entry.access_count += 1
                entry.last_access = time.time()
                return entry
            return None

    async def add_entry(self, entry: CacheEntry) -> bool:
        """
        Add entry to cache, evicting if necessary.

        Returns:
            True if added successfully, False if cache full and couldn't evict
        """
        async with self._lock:
            key = entry.key()

            # Already cached
            if key in self.entries:
                return True

            # Check if we need to evict
            if self.get_size_mb() + entry.size_mb() > self.max_size_mb:
                evicted = await self._evict_to_make_room(entry.size_mb())
                if not evicted:
                    logger.warning(f"{self.name}: Could not make room for {key}")
                    return False

            self.entries[key] = entry
            logger.debug(f"{self.name}: Added {key} (size: {self.get_size_mb():.1f}MB)")
            return True

    async def _evict_to_make_room(self, needed_mb: float) -> bool:
        """
        Evict entries to make room.

        Eviction policy: LRU + lowest probability first
        """
        if not self.entries:
            return False

        # Sort by: probability (ascending), then last_access (ascending)
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: (e.probability, e.last_access)
        )

        freed_mb = 0.0
        keys_to_remove = []

        for entry in sorted_entries:
            keys_to_remove.append(entry.key())
            freed_mb += entry.size_mb()

            if freed_mb >= needed_mb:
                break

        # Remove entries
        for key in keys_to_remove:
            del self.entries[key]
            logger.debug(f"{self.name}: Evicted {key}")

        return freed_mb >= needed_mb

    async def clear(self):
        """Clear all entries (with locking)."""
        async with self._lock:
            self.entries.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.entries:
            return {
                'size_mb': 0.0,
                'count': 0,
                'utilization': 0.0
            }

        return {
            'size_mb': self.get_size_mb(),
            'count': len(self.entries),
            'utilization': self.get_size_mb() / self.max_size_mb,
            'avg_access_count': sum(e.access_count for e in self.entries.values()) / len(self.entries)
        }


class BranchPredictor:
    """
    Predicts future playback scenarios (preset switches, seeks, etc.).

    Similar to CPU branch prediction, learns from history and predicts likely paths.
    """

    def __init__(self):
        # Track preset switch patterns: (from_preset, to_preset) -> count
        self.transition_matrix: Dict[Tuple[str, str], int] = defaultdict(int)

        # Track recent switches (last 100)
        self.recent_switches: List[Tuple[str, str, float]] = []  # (from, to, timestamp)

        # Prediction accuracy tracking
        self.predictions_made = 0
        self.predictions_correct = 0

    def record_switch(self, from_preset: str, to_preset: str):
        """
        Record a preset switch for learning.
        """
        self.transition_matrix[(from_preset, to_preset)] += 1
        self.recent_switches.append((from_preset, to_preset, time.time()))

        # Keep only recent history
        if len(self.recent_switches) > 100:
            self.recent_switches.pop(0)

        logger.debug(f"Branch predictor: Recorded {from_preset} -> {to_preset}")

    def predict_next_presets(self, current_preset: str, top_n: int = 3) -> List[Tuple[str, float]]:
        """
        Predict most likely next presets.

        Args:
            current_preset: Current preset
            top_n: Number of predictions to return

        Returns:
            List of (preset, probability) sorted by probability descending
        """
        # Get transition probabilities from current preset
        transitions = {
            to_preset: count
            for (from_p, to_preset), count in self.transition_matrix.items()
            if from_p == current_preset
        }

        # If no history, use default priorities
        if not transitions:
            default_probs = {
                'adaptive': 0.5,
                'gentle': 0.2,
                'warm': 0.15,
                'bright': 0.1,
                'punchy': 0.05
            }
            # Remove current preset from defaults
            if current_preset in default_probs:
                del default_probs[current_preset]

            sorted_defaults = sorted(default_probs.items(), key=lambda x: x[1], reverse=True)
            return sorted_defaults[:top_n]

        # Calculate probabilities
        total = sum(transitions.values())
        probs = {preset: count / total for preset, count in transitions.items()}

        # Boost presets used recently in this session
        recent_time_window = time.time() - 300  # Last 5 minutes
        recent_presets = [
            to_p for from_p, to_p, ts in self.recent_switches
            if ts > recent_time_window and from_p == current_preset
        ]

        for preset in recent_presets:
            if preset in probs:
                probs[preset] *= 1.5

        # Sort and return top N
        sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        return sorted_probs[:top_n]

    def predict_branches(
        self,
        current_preset: str,
        current_chunk: int,
        position: float
    ) -> List[BranchScenario]:
        """
        Generate branch scenarios for L2 cache.

        Returns:
            List of BranchScenario objects
        """
        branches = []

        # Scenario 1: User continues on current preset (baseline)
        branches.append(BranchScenario(
            name="continue_current",
            preset=current_preset,
            chunk_range=range(current_chunk + 2, current_chunk + 5),
            probability=0.6
        ))

        # Scenario 2-4: User switches to predicted presets
        predicted_presets = self.predict_next_presets(current_preset, top_n=3)
        for i, (preset, base_prob) in enumerate(predicted_presets):
            # Decrease probability for lower-ranked predictions
            adjusted_prob = base_prob * 0.3 / (i + 1)

            branches.append(BranchScenario(
                name=f"switch_to_{preset}",
                preset=preset,
                chunk_range=range(current_chunk + 1, current_chunk + 3),
                probability=adjusted_prob
            ))

        # Scenario 5: User seeks forward (common in long tracks)
        if position > 120:  # After 2 minutes, seeking becomes more likely
            branches.append(BranchScenario(
                name="seek_forward",
                preset=current_preset,
                chunk_range=range(current_chunk + 10, current_chunk + 12),
                probability=0.05
            ))

        return branches

    def update_accuracy(self, predicted: bool):
        """
        Update prediction accuracy metrics.

        Args:
            predicted: True if prediction was correct
        """
        self.predictions_made += 1
        if predicted:
            self.predictions_correct += 1

    def get_accuracy(self) -> float:
        """Get current prediction accuracy."""
        if self.predictions_made == 0:
            return 0.0
        return self.predictions_correct / self.predictions_made

    async def predict_with_audio_content(
        self,
        current_preset: str,
        filepath: Optional[str] = None,
        current_chunk: int = 0,
        top_n: int = 3
    ) -> List[Tuple[str, float]]:
        """
        Enhanced prediction combining user behavior with audio content analysis.

        Args:
            current_preset: Current preset
            filepath: Path to audio file (for audio analysis)
            current_chunk: Current chunk index
            top_n: Number of predictions to return

        Returns:
            List of (preset, probability) tuples
        """
        # Get user behavior predictions
        user_predictions = self.predict_next_presets(current_preset, top_n=5)

        # If no filepath, return user predictions only
        if not filepath:
            return user_predictions[:top_n]

        try:
            # Import audio predictor (lazy import to avoid circular dependency)
            from audio_content_predictor import get_audio_content_predictor

            predictor = get_audio_content_predictor()

            # Analyze next chunk for audio-aware prediction
            next_chunk = current_chunk + 1
            audio_scores = await predictor.predict_preset_for_chunk(
                filepath=filepath,
                chunk_idx=next_chunk
            )

            # Combine user behavior (70%) with audio content (30%)
            combined = predictor.combine_with_user_prediction(
                user_predictions=user_predictions,
                audio_scores=audio_scores,
                user_weight=0.7,
                audio_weight=0.3
            )

            return combined[:top_n]

        except Exception as e:
            logger.warning(f"Audio-aware prediction failed, using user-only: {e}")
            return user_predictions[:top_n]


class MultiTierBufferManager:
    """
    Multi-tier buffer manager with L1/L2/L3 caching and branch prediction.

    Inspired by CPU cache hierarchies, optimized for audio chunk processing.
    """

    def __init__(self):
        # Cache tiers
        self.l1_cache = CacheTier("L1", L1_MAX_SIZE_MB)
        self.l2_cache = CacheTier("L2", L2_MAX_SIZE_MB)
        self.l3_cache = CacheTier("L3", L3_MAX_SIZE_MB)

        # Branch predictor
        self.branch_predictor = BranchPredictor()

        # Current playback state
        self.current_track_id: Optional[int] = None
        self.current_position: float = 0.0
        self.current_preset: str = "adaptive"
        self.intensity: float = 1.0

        # Metrics
        self.l1_hits = 0
        self.l1_misses = 0
        self.l2_hits = 0
        self.l2_misses = 0
        self.l3_hits = 0
        self.l3_misses = 0

        # Session tracking
        self.session_start = time.time()
        self.preset_switches_in_session = 0

        # Lock for state updates
        self._lock = asyncio.Lock()

        # Throttling and debouncing (robustness)
        self.last_position_update_time = 0.0
        self.position_update_throttle_ms = 100  # 100ms minimum between updates
        self.last_preset_change_time = 0.0
        self.preset_change_debounce_ms = 500  # 500ms minimum between preset changes
        self.rapid_interaction_window = []  # Track recent interactions
        self.rapid_interaction_threshold = 10  # 10 interactions in 1 second = rapid

    def _get_current_chunk(self, position: float) -> int:
        """Calculate which chunk contains the given position."""
        return int(position // CHUNK_DURATION)

    async def update_position(
        self,
        track_id: int,
        position: float,
        preset: str = "adaptive",
        intensity: float = 1.0
    ):
        """
        Update current playback position and trigger buffer updates.

        Args:
            track_id: Current track ID
            position: Current position in seconds
            preset: Current preset
            intensity: Processing intensity (0.0-1.0)
        """
        current_time = time.time()

        # Check if track changed (bypass throttle for track changes)
        track_changed = track_id != self.current_track_id

        # Throttle position updates (100ms minimum), but NOT for track changes
        if not track_changed:
            if (current_time - self.last_position_update_time) < (self.position_update_throttle_ms / 1000.0):
                logger.debug("Position update throttled")
                return

        self.last_position_update_time = current_time

        # Detect rapid interactions (10+ in 1 second)
        self.rapid_interaction_window.append(current_time)
        self.rapid_interaction_window = [t for t in self.rapid_interaction_window if current_time - t < 1.0]

        is_rapid_interaction = len(self.rapid_interaction_window) >= self.rapid_interaction_threshold
        if is_rapid_interaction:
            logger.warning(f"Rapid interaction detected ({len(self.rapid_interaction_window)} updates in 1s) - user exploring")

        async with self._lock:
            # Detect preset switch
            preset_changed = preset != self.current_preset
            if preset_changed and self.current_preset:
                # Debounce preset changes (500ms minimum)
                if (current_time - self.last_preset_change_time) < (self.preset_change_debounce_ms / 1000.0):
                    logger.debug("Preset change debounced")
                    # Don't record this switch for learning (too rapid)
                else:
                    # Only record if not rapid interaction
                    if not is_rapid_interaction:
                        self.branch_predictor.record_switch(self.current_preset, preset)
                        self.preset_switches_in_session += 1
                        self.last_preset_change_time = current_time
                    else:
                        logger.debug("Skipping preset switch recording during rapid interaction")

            # Handle track change (detected earlier to bypass throttling)
            if track_changed:
                await self._handle_track_change(track_id)

            # Update state
            self.current_track_id = track_id
            self.current_position = position
            self.current_preset = preset
            self.intensity = intensity

            current_chunk = self._get_current_chunk(position)

            logger.debug(
                f"Position update: track={track_id}, pos={position:.1f}s, "
                f"chunk={current_chunk}, preset={preset}"
            )

            # Update cache tiers based on new position
            await self._update_cache_tiers(track_id, current_chunk, preset, intensity)

    async def _handle_track_change(self, new_track_id: int):
        """Handle track change - clear caches for old track."""
        logger.info(f"Track changed: {self.current_track_id} -> {new_track_id}")

        # Clear all caches (could be optimized to keep some L3 if tracks are related)
        await self.l1_cache.clear()
        await self.l2_cache.clear()
        await self.l3_cache.clear()

        logger.info("Cleared all caches for track change")

    async def _update_cache_tiers(
        self,
        track_id: int,
        current_chunk: int,
        preset: str,
        intensity: float
    ):
        """
        Update all cache tiers based on current playback position.

        This is the core logic that determines what to cache where.
        """
        # L1: Current + next chunk for high-probability presets
        await self._update_l1_cache(track_id, current_chunk, preset, intensity)

        # L2: Branch scenarios (predicted preset switches)
        await self._update_l2_cache(track_id, current_chunk, preset, intensity)

        # L3: Long-term cache for current preset
        await self._update_l3_cache(track_id, current_chunk, preset, intensity)

    async def _update_l1_cache(
        self,
        track_id: int,
        current_chunk: int,
        preset: str,
        intensity: float
    ):
        """
        Update L1 cache with current + next chunk for high-probability presets.
        """
        # Always include current preset
        top_presets = [preset]

        # Add predicted presets
        predicted = self.branch_predictor.predict_next_presets(preset, top_n=2)
        for pred_preset, prob in predicted:
            if prob > 0.15:  # Only high-confidence predictions in L1
                top_presets.append(pred_preset)

        # Limit to top 3 to fit in L1
        top_presets = top_presets[:3]

        # Cache current and next chunk for these presets
        for chunk_offset in [0, 1]:
            chunk_idx = current_chunk + chunk_offset
            for cache_preset in top_presets:
                entry = CacheEntry(
                    track_id=track_id,
                    preset=cache_preset,
                    chunk_idx=chunk_idx,
                    intensity=intensity,
                    timestamp=time.time(),
                    probability=1.0 if cache_preset == preset else 0.5
                )
                await self.l1_cache.add_entry(entry)

    async def _update_l2_cache(
        self,
        track_id: int,
        current_chunk: int,
        preset: str,
        intensity: float
    ):
        """
        Update L2 cache with branch scenario predictions.
        """
        # Get branch scenarios from predictor
        branches = self.branch_predictor.predict_branches(
            preset, current_chunk, self.current_position
        )

        # Cache chunks for each branch scenario
        for branch in branches:
            for chunk_idx in branch.chunk_range:
                entry = CacheEntry(
                    track_id=track_id,
                    preset=branch.preset,
                    chunk_idx=chunk_idx,
                    intensity=intensity,
                    timestamp=time.time(),
                    probability=branch.probability
                )
                await self.l2_cache.add_entry(entry)

    async def _update_l3_cache(
        self,
        track_id: int,
        current_chunk: int,
        preset: str,
        intensity: float
    ):
        """
        Update L3 cache with long-term buffer for current preset only.
        """
        # Buffer 5-10 chunks ahead for current preset
        for offset in range(2, 10):
            chunk_idx = current_chunk + offset
            entry = CacheEntry(
                track_id=track_id,
                preset=preset,
                chunk_idx=chunk_idx,
                intensity=intensity,
                timestamp=time.time(),
                probability=0.8  # Lower priority than L1/L2
            )
            await self.l3_cache.add_entry(entry)

    async def is_chunk_cached(
        self,
        track_id: int,
        preset: str,
        chunk_idx: int,
        intensity: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if chunk is cached in any tier.

        Returns:
            (is_cached, tier_name) - tier_name is "L1", "L2", "L3", or None
        """
        key = f"{track_id}_{preset}_{intensity:.1f}_{chunk_idx}"

        # Check L1 first
        if await self.l1_cache.get_entry(key):
            self.l1_hits += 1
            return True, "L1"

        # Check L2
        if await self.l2_cache.get_entry(key):
            self.l2_hits += 1
            return True, "L2"

        # Check L3
        if await self.l3_cache.get_entry(key):
            self.l3_hits += 1
            return True, "L3"

        # Cache miss
        self.l1_misses += 1
        return False, None

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics.

        Returns:
            Dictionary with stats for each tier and overall metrics
        """
        total_requests = (self.l1_hits + self.l1_misses +
                         self.l2_hits + self.l3_hits)

        return {
            'l1': {
                **self.l1_cache.get_stats(),
                'hits': self.l1_hits,
                'misses': self.l1_misses,
                'hit_rate': self.l1_hits / max(1, self.l1_hits + self.l1_misses)
            },
            'l2': {
                **self.l2_cache.get_stats(),
                'hits': self.l2_hits,
                'hit_rate': self.l2_hits / max(1, total_requests) if total_requests > 0 else 0.0
            },
            'l3': {
                **self.l3_cache.get_stats(),
                'hits': self.l3_hits,
                'hit_rate': self.l3_hits / max(1, total_requests) if total_requests > 0 else 0.0
            },
            'overall': {
                'total_hits': self.l1_hits + self.l2_hits + self.l3_hits,
                'total_misses': self.l1_misses + self.l2_misses + self.l3_misses,
                'overall_hit_rate': (self.l1_hits + self.l2_hits + self.l3_hits) / max(1, total_requests),
                'total_size_mb': (self.l1_cache.get_size_mb() +
                                 self.l2_cache.get_size_mb() +
                                 self.l3_cache.get_size_mb())
            },
            'prediction': {
                'accuracy': self.branch_predictor.get_accuracy(),
                'switches_in_session': self.preset_switches_in_session,
                'session_duration_minutes': (time.time() - self.session_start) / 60
            }
        }

    async def clear_all_caches(self):
        """Clear all cache tiers."""
        await self.l1_cache.clear()
        await self.l2_cache.clear()
        await self.l3_cache.clear()
        logger.info("Cleared all cache tiers")

    async def handle_track_deleted(self, track_id: int):
        """
        Handle track deletion from library.

        Removes all cache entries for the deleted track to prevent stale data.

        Args:
            track_id: ID of the deleted track
        """
        logger.info(f"Track {track_id} deleted - cleaning up caches")

        removed_count = 0

        # Remove all cache entries for this track
        for tier in [self.l1_cache, self.l2_cache, self.l3_cache]:
            async with tier._lock:
                entries_to_remove = [
                    key for key, entry in tier.entries.items()
                    if entry.track_id == track_id
                ]
                for key in entries_to_remove:
                    del tier.entries[key]
                    removed_count += 1

        logger.info(f"Removed {removed_count} cache entries for deleted track {track_id}")

    async def handle_track_modified(self, track_id: int, filepath: str):
        """
        Handle track file modification (file changed on disk).

        Invalidates caches for the modified track.

        Args:
            track_id: ID of the modified track
            filepath: Path to the modified file
        """
        logger.info(f"Track {track_id} modified - invalidating caches")

        # Clear audio content cache for this file
        try:
            from audio_content_predictor import get_audio_content_predictor
            predictor = get_audio_content_predictor()

            # Remove all cached analysis for this file
            cache_keys_to_remove = [
                key for key in predictor.analyzer.analysis_cache.keys()
                if key.startswith(f"{filepath}_")
            ]
            for key in cache_keys_to_remove:
                del predictor.analyzer.analysis_cache[key]

            logger.debug(f"Cleared {len(cache_keys_to_remove)} audio analysis cache entries")

        except Exception as e:
            logger.warning(f"Could not clear audio analysis cache: {e}")

        # Clear processed chunk caches for this track
        await self.handle_track_deleted(track_id)

        logger.info(f"Cache invalidation complete for track {track_id}")


# Global instance
multi_tier_buffer_manager = MultiTierBufferManager()

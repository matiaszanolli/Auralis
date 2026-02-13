"""
Analysis Extractor with Caching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extracts track-level audio analysis (fingerprint, tempo, genre, mastering targets)
and automatically caches results to avoid redundant per-chunk analysis.

This module bridges ContentAnalyzer with TrackAnalysisCache to provide:
1. One-time track-level analysis extraction
2. Automatic caching of expensive operations (fingerprint, tempo, genre)
3. Reuse of cached analysis across all chunks

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import Any, cast

import numpy as np

from auralis.core.analysis.content_analyzer import ContentAnalyzer
from auralis.io.unified_loader import load_audio

from .track_analysis_cache import get_track_analysis_cache

logger = logging.getLogger(__name__)


class AnalysisExtractor:
    """
    Extract and cache track-level audio analysis.

    Workflow:
    1. Check if analysis cached for track
    2. If cached, return immediately (< 1ms)
    3. If not cached:
       a. Load track audio
       b. Extract 25D fingerprint (200-500ms)
       c. Extract content profile with tempo/genre (500-1000ms)
       d. Cache results
       e. Return to caller

    Key design:
    - Caches at TRACK level, not chunk level
    - Reuses cached analysis across all chunks
    - Minimal overhead on cache hit (< 1ms)
    - Saves 4-12 seconds per playback session

    Integration points:
    - ChunkedAudioProcessor: Call before processing first chunk
    - HybridProcessor: Use cached analysis instead of per-chunk analysis
    - StreamlinedCacheWorker: Populate cache during initial processing
    """

    def __init__(self, sample_rate: int = 44100):
        """
        Initialize analysis extractor.

        Args:
            sample_rate: Audio sample rate (default 44100 Hz)
        """
        self.sample_rate = sample_rate
        self.cache = get_track_analysis_cache()

        # Initialize analyzers (reuse across extractions)
        self.content_analyzer = ContentAnalyzer(
            sample_rate=sample_rate,
            use_ml_classification=True,
            use_fingerprint_analysis=True,
            use_tempo_detection=True
        )

        logger.debug(f"AnalysisExtractor initialized: sr={sample_rate}Hz")

    def extract_or_get(
        self,
        track_id: int,
        filepath: str,
        force_recompute: bool = False
    ) -> dict[str, Any]:
        """
        Get cached track analysis or extract if not cached.

        Cache-hit path (< 1ms):
        - Track analysis already computed and cached
        - Return cached results immediately

        Cache-miss path (1-2 seconds):
        - Load track audio
        - Extract 25D fingerprint (200-500ms)
        - Extract content profile with tempo/genre (300-1000ms)
        - Cache results
        - Return to caller

        Args:
            track_id: Track ID to analyze
            filepath: Path to audio file
            force_recompute: Force recomputation even if cached

        Returns:
            Dictionary with keys:
            - fingerprint: Dict[str, float] (25 dimensions)
            - content_profile: Dict[str, Any] (basic features, tempo, genre)
            - mastering_targets: Dict[str, float] (derived from fingerprint)
            - tempo_bpm: float (from fingerprint or content analysis)
            - genre: str (primary genre classification)
            - timestamp: datetime (when extracted)
        """
        # Check cache first
        if not force_recompute:
            cached = self.cache.get(track_id)
            if cached is not None:
                logger.info(f"Using cached analysis for track {track_id}")
                return cast(dict[str, Any], cached)

        # Cache miss - extract analysis
        logger.info(f"Extracting analysis for track {track_id} (not cached)")
        analysis = self._extract_analysis(track_id, filepath)

        # Store in cache
        self.cache.put(track_id, analysis)

        return analysis

    def get_cached_analysis(self, track_id: int) -> dict[str, Any] | None:
        """
        Get cached analysis without recomputing.

        Returns None if not cached (different from extract_or_get which would compute).

        Use this when you want to check if analysis exists without triggering extraction.

        Args:
            track_id: Track ID

        Returns:
            Cached analysis or None if not cached
        """
        return cast(dict[str, Any | None], self.cache.get(track_id))

    def prefetch_analysis(self, track_id: int, filepath: str) -> bool:
        """
        Prefetch analysis in background without blocking.

        Useful for preparing analysis for next track in queue before playback starts.

        Args:
            track_id: Track ID
            filepath: Path to audio file

        Returns:
            True if extraction started, False if already cached
        """
        if self.cache.has(track_id):
            logger.debug(f"Track {track_id} already cached, skipping prefetch")
            return False

        try:
            self.extract_or_get(track_id, filepath)
            return True
        except Exception as e:
            logger.error(f"Prefetch failed for track {track_id}: {e}")
            return False

    def clear_cache(self, track_id: int | None = None) -> None:
        """
        Clear cache entry(ies).

        Args:
            track_id: Specific track to clear, or None to clear all
        """
        self.cache.clear(track_id)

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics (size, count, memory usage)
        """
        return cast(dict[str, Any], self.cache.get_stats())

    def _extract_analysis(self, track_id: int, filepath: str) -> dict[str, Any]:
        """
        Extract track-level analysis from audio file.

        Steps:
        1. Load entire track audio
        2. Extract 25D fingerprint (200-500ms)
        3. Extract content profile with tempo/genre (300-1000ms)
        4. Derive mastering targets from fingerprint

        Args:
            track_id: Track ID (for logging)
            filepath: Path to audio file

        Returns:
            Complete analysis dictionary
        """
        import time
        from datetime import datetime

        start_time = time.time()

        try:
            # Step 1: Load entire track
            logger.debug(f"Loading track {track_id} for analysis")
            audio, sr = load_audio(filepath)

            if audio is None:
                raise ValueError(f"Failed to load audio from {filepath}")

            # Ensure mono for analysis
            if audio.ndim == 2:
                audio = np.mean(audio, axis=0)

            # Resample to target sample rate if needed
            if sr != self.sample_rate:
                logger.debug(f"Resampling from {sr}Hz to {self.sample_rate}Hz")
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
                sr = self.sample_rate

            # Step 2: Extract 25D fingerprint
            logger.debug(f"Extracting 25D fingerprint for track {track_id}")
            fingerprint_start = time.time()
            fingerprint = self.content_analyzer.fingerprint_analyzer.analyze(audio, sr)
            fingerprint_time = time.time() - fingerprint_start

            # Step 3: Extract content profile
            logger.debug(f"Extracting content profile for track {track_id}")
            profile_start = time.time()
            content_profile = self.content_analyzer.analyze_content(audio)
            profile_time = time.time() - profile_start

            # Step 4: Derive mastering targets from fingerprint
            # (This will be integrated with AdaptiveMasteringEngine)
            mastering_targets = self._derive_mastering_targets(fingerprint, content_profile)

            total_time = time.time() - start_time

            analysis = {
                'track_id': track_id,
                'fingerprint': fingerprint,
                'content_profile': content_profile,
                'mastering_targets': mastering_targets,
                'tempo_bpm': fingerprint.get('tempo_bpm', content_profile.get('estimated_tempo', 120.0)),
                'genre': content_profile.get('genre_info', {}).get('primary', 'unknown'),
                'timestamp': datetime.now(),
                'extraction_time_ms': {
                    'fingerprint': round(fingerprint_time * 1000, 1),
                    'profile': round(profile_time * 1000, 1),
                    'total': round(total_time * 1000, 1),
                }
            }

            logger.info(
                f"Analysis extracted for track {track_id}: "
                f"fingerprint={analysis['extraction_time_ms']['fingerprint']}ms, "
                f"profile={analysis['extraction_time_ms']['profile']}ms, "
                f"total={analysis['extraction_time_ms']['total']}ms"
            )

            return analysis

        except Exception as e:
            logger.error(f"Analysis extraction failed for track {track_id}: {e}", exc_info=True)
            # Return minimal analysis on failure
            return {
                'track_id': track_id,
                'fingerprint': None,
                'content_profile': None,
                'mastering_targets': None,
                'tempo_bpm': 120.0,
                'genre': 'unknown',
                'timestamp': datetime.now(),
                'error': str(e),
                'extraction_time_ms': {
                    'fingerprint': 0,
                    'profile': 0,
                    'total': 0,
                }
            }

    def _derive_mastering_targets(
        self,
        fingerprint: dict[str, float],
        content_profile: dict[str, Any]
    ) -> dict[str, float]:
        """
        Derive adaptive mastering targets from fingerprint.

        This is a simplified version. Full integration with AdaptiveMasteringEngine
        would happen in the next phase.

        Args:
            fingerprint: 25D fingerprint dictionary
            content_profile: Content analysis profile

        Returns:
            Dictionary with mastering target parameters
        """
        if not fingerprint:
            return {}

        # Extract key characteristics
        lufs = fingerprint.get('lufs', -18.0)
        fingerprint.get('crest_db', 6.0)
        fingerprint.get('bass_pct', 0.0) + fingerprint.get('low_mid_pct', 0.0)

        # Basic adaptive targets (full logic would be in AdaptiveMasteringEngine)
        targets = {
            'target_lufs': -14.0,  # Adaptive based on content
            'target_crest': 6.0,   # Adaptive based on dynamics
            'bass_boost': 0.0,      # Adaptive based on bass content
            'clarity_boost': 0.0,   # Adaptive based on midrange
            'presence_boost': 0.0,  # Adaptive based on presence
        }

        # Adjust based on content
        if lufs < -20.0:
            targets['clarity_boost'] = 1.5
        elif lufs > -10.0:
            targets['bass_boost'] = -1.0

        return targets

"""
Mastering Target Service
~~~~~~~~~~~~~~~~~~~~~~~~~

Centralized fingerprint loading and mastering target generation.

Consolidates duplicate logic from:
- chunked_processor._load_fingerprint_from_database()
- chunked_processor._generate_targets_from_fingerprint()
- chunked_processor fingerprint extraction in process_chunk()

This service eliminates ~200 lines of duplicate fingerprint/target management.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import hashlib
import logging
import threading
import traceback
from pathlib import Path
from typing import Any
from collections.abc import Callable

import soundfile as sf
from auralis.analysis.fingerprint import AudioFingerprintAnalyzer, FingerprintStorage
from auralis.analysis.mastering_fingerprint import MasteringFingerprint
from auralis.io.unified_loader import load_audio
from mutagen import File as MutagenFile  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)


class MasteringTargetService:
    """
    Centralized fingerprint loading and mastering target generation.

    Provides 3-tier fingerprint loading hierarchy:
    1. Database (fastest - cached in SQLite)
    2. .25d file (fast - pre-computed)
    3. Extract from audio (slow - requires full analysis)

    Features:
    - Thread-safe caching with RLock
    - Automatic target generation from fingerprints
    - One-stop method for getting fingerprint + targets
    - Supports saving extracted fingerprints
    - Repository pattern via dependency injection
    """

    def __init__(
        self,
        cache: dict[str, Any] | None = None,
        get_fingerprints_repository: Callable[[], Any] | None = None
    ):
        """
        Initialize mastering target service.

        Args:
            cache: Optional shared cache dictionary
            get_fingerprints_repository: Callable that returns fingerprints repository
                                        (for database lookups via repository pattern)
        """
        self.cache = cache if cache is not None else {}
        self._get_fingerprints_repository = get_fingerprints_repository
        self._lock = threading.RLock()
        logger.debug("MasteringTargetService initialized")

    def _get_cache_key(self, track_id: int, filepath: str) -> str:
        """Generate cache key for fingerprint."""
        # Use both track_id and file signature for uniqueness
        file_hash = hashlib.md5(filepath.encode()).hexdigest()[:8]
        return f"fingerprint_{track_id}_{file_hash}"

    def load_fingerprint_from_database(
        self,
        track_id: int
    ) -> Any | None:
        """
        Load fingerprint from database (Tier 1 - fastest).

        Consolidates logic from chunked_processor._load_fingerprint_from_database().

        Args:
            track_id: Track ID to look up

        Returns:
            MasteringFingerprint instance or None if not found
        """
        # Require repository factory (dependency injection pattern)
        if self._get_fingerprints_repository is None:
            logger.debug("No fingerprints repository provided - skipping database lookup")
            return None

        try:
            # Get repository via dependency injection
            fingerprints_repo = self._get_fingerprints_repository()

            # Try to get fingerprint from database
            fp_record = fingerprints_repo.get_by_track_id(track_id)

            if fp_record:
                # Convert database record to MasteringFingerprint
                fp_dict = {
                    'sub_bass_pct': fp_record.sub_bass_pct,
                    'bass_pct': fp_record.bass_pct,
                    'low_mid_pct': fp_record.low_mid_pct,
                    'mid_pct': fp_record.mid_pct,
                    'upper_mid_pct': fp_record.upper_mid_pct,
                    'presence_pct': fp_record.presence_pct,
                    'air_pct': fp_record.air_pct,
                    'lufs': fp_record.lufs,
                    'crest_db': fp_record.crest_db,
                    'bass_mid_ratio': fp_record.bass_mid_ratio,
                    'tempo_bpm': fp_record.tempo_bpm,
                    'rhythm_stability': fp_record.rhythm_stability,
                    'transient_density': fp_record.transient_density,
                    'silence_ratio': fp_record.silence_ratio,
                    'spectral_centroid': fp_record.spectral_centroid,
                    'spectral_rolloff': fp_record.spectral_rolloff,
                    'spectral_flatness': fp_record.spectral_flatness,
                    'harmonic_ratio': fp_record.harmonic_ratio,
                    'pitch_stability': fp_record.pitch_stability,
                    'chroma_energy': fp_record.chroma_energy,
                    'dynamic_range_variation': fp_record.dynamic_range_variation,
                    'loudness_variation_std': fp_record.loudness_variation_std,
                    'peak_consistency': fp_record.peak_consistency,
                    'stereo_width': fp_record.stereo_width,
                    'phase_correlation': fp_record.phase_correlation,
                }

                fingerprint = MasteringFingerprint(**fp_dict)
                logger.info(
                    f"✅ Loaded fingerprint from database for track {track_id} "
                    f"(LUFS: {fp_record.lufs:.1f}, Crest: {fp_record.crest_db:.1f})"
                )
                return fingerprint
            else:
                logger.debug(f"No fingerprint in database for track {track_id}")
                return None

        except Exception as e:
            logger.debug(f"Database fingerprint lookup failed for track {track_id}: {e}")
            return None

    def load_fingerprint_from_file(
        self,
        filepath: str
    ) -> tuple[Any, dict[str, Any] | None] | None:
        """
        Load fingerprint from .25d file (Tier 2 - fast).

        Args:
            filepath: Path to audio file (will look for .25d sidecar)

        Returns:
            Tuple of (fingerprint, mastering_targets) or None if not found
        """
        try:
            cached_data = FingerprintStorage.load(Path(filepath))
            if cached_data:
                fingerprint, mastering_targets = cached_data
                logger.info(f"✅ Loaded fingerprint from .25d file for {Path(filepath).name}")
                return (fingerprint, mastering_targets)
            else:
                logger.debug(f"No .25d file found for {Path(filepath).name}")
                return None

        except Exception as e:
            logger.debug(f".25d file loading failed for {filepath}: {e}")
            return None

    def extract_fingerprint_from_audio(
        self,
        filepath: str,
        sample_rate: int | None = None,
        save_to_file: bool = True
    ) -> tuple[Any, dict[str, Any] | None] | None:
        """
        Extract fingerprint from audio file (Tier 3 - slow).

        Uses PyO3 Rust fingerprinting for fast, accurate analysis.

        Args:
            filepath: Path to audio file
            sample_rate: Optional target sample rate for loading
            save_to_file: If True, save extracted fingerprint to .25d file

        Returns:
            Tuple of (fingerprint, mastering_targets) or None if extraction fails
        """
        try:
            logger.info(f"🔍 Extracting fingerprint from audio: {Path(filepath).name}")

            # Try to use PyO3 Rust fingerprinting
            try:
                from auralis_dsp import compute_fingerprint

                # Load audio file
                full_audio, sr = sf.read(filepath, dtype='float32')

                # Handle stereo/mono
                if full_audio.ndim == 1:
                    channels = 1
                    audio_array = full_audio
                else:
                    channels = full_audio.shape[1] if full_audio.ndim == 2 else 1
                    # For stereo, interleave L,R channels
                    if channels == 2 and full_audio.ndim == 2:
                        audio_array = full_audio.flatten(order='F')
                    else:
                        audio_array = full_audio

                logger.debug(f"Audio loaded via soundfile: {len(audio_array)} samples, SR={sr}, CH={channels}")

                # Call PyO3 Rust fingerprinting
                fingerprint_data = compute_fingerprint(audio_array, sr, channels)
                logger.info(f"✅ PyO3 Rust extracted fingerprint for {Path(filepath).name}")

            except (ImportError, Exception) as e:
                logger.warning(f"PyO3 fingerprinting failed ({e}), falling back to Python analyzer...")

                # Fallback to Python-based analyzer
                full_audio, sr = load_audio(filepath, target_sample_rate=sample_rate)
                analyzer = AudioFingerprintAnalyzer()
                fingerprint_data = analyzer.analyze(full_audio, sr)

            if fingerprint_data is not None:
                # Add metadata for .25d file
                try:
                    audio_file = MutagenFile(filepath)
                    duration_value: float = (
                        float(audio_file.info.length) if audio_file else len(full_audio) / sr
                    )
                except Exception:
                    duration_value = len(full_audio) / sr

                fingerprint_data['_metadata'] = {  # type: ignore[assignment]
                    'duration': duration_value,
                    'sample_rate': sr
                }

                # Generate mastering targets from fingerprint
                mastering_targets = self.generate_targets_from_fingerprint(fingerprint_data)

                # Save to .25d file if requested
                if save_to_file:
                    FingerprintStorage.save(Path(filepath), fingerprint_data, mastering_targets)
                    logger.info(f"💾 Saved fingerprint to .25d file for {Path(filepath).name}")

                return (fingerprint_data, mastering_targets)
            else:
                logger.error(f"Fingerprint extraction returned None for {filepath}")
                return None

        except Exception as e:
            logger.error(f"Fingerprint extraction failed for {filepath}: {e}")
            logger.debug(traceback.format_exc())
            return None

    def load_fingerprint(
        self,
        track_id: int,
        filepath: str,
        extract_if_missing: bool = True,
        save_extracted: bool = True
    ) -> tuple[Any, dict[str, Any] | None] | None:
        """
        Load fingerprint using 3-tier hierarchy.

        1. Database (fastest)
        2. .25d file
        3. Extract from audio (if extract_if_missing=True)

        Args:
            track_id: Track ID for database lookup
            filepath: Path to audio file
            extract_if_missing: If True, extract from audio if not cached
            save_extracted: If True, save extracted fingerprint to .25d file

        Returns:
            Tuple of (fingerprint, mastering_targets) or None if not found
        """
        # Check cache first
        cache_key = self._get_cache_key(track_id, filepath)
        with self._lock:
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if isinstance(cached, tuple) and len(cached) == 2:
                    logger.debug(f"Using cached fingerprint for track {track_id}")
                    return cached

        # Tier 1: Try database
        fingerprint = self.load_fingerprint_from_database(track_id)
        if fingerprint is not None:
            # Generate targets from database fingerprint
            targets = self.generate_targets_from_fingerprint(fingerprint)
            result = (fingerprint, targets)

            # Cache result
            with self._lock:
                self.cache[cache_key] = result

            return result

        # Tier 2: Try .25d file
        file_result = self.load_fingerprint_from_file(filepath)
        if file_result is not None:
            # Cache result
            with self._lock:
                self.cache[cache_key] = file_result

            return file_result

        # Tier 3: Extract from audio (if requested)
        if extract_if_missing:
            extract_result = self.extract_fingerprint_from_audio(
                filepath,
                save_to_file=save_extracted
            )

            if extract_result is not None:
                # Cache result
                with self._lock:
                    self.cache[cache_key] = extract_result

                return extract_result

        logger.debug(f"No fingerprint found for track {track_id}")
        return None

    def generate_targets_from_fingerprint(
        self,
        fingerprint: Any
    ) -> dict[str, Any]:
        """
        Generate mastering targets from 25D fingerprint.

        Consolidates logic from chunked_processor._generate_targets_from_fingerprint().

        This converts acoustic characteristics into processing parameters.
        Targets remain fixed for the entire track, enabling fast processing.

        Args:
            fingerprint: MasteringFingerprint instance or dict

        Returns:
            Dictionary of mastering targets
        """
        # Handle both dict and MasteringFingerprint objects
        if hasattr(fingerprint, '__dict__'):
            fp_dict = fingerprint.__dict__
        else:
            fp_dict = fingerprint

        # Get frequency and dynamics data
        freq = fp_dict.get('frequency', {})
        dynamics = fp_dict.get('dynamics', {})

        # Target loudness based on current LUFS
        fp_dict.get('lufs', dynamics.get('lufs', -14.0))
        target_lufs = -14.0  # Standard streaming loudness

        # Target crest factor (preserve dynamic range character)
        current_crest = fp_dict.get('crest_db', dynamics.get('crest_db', 12.0))
        target_crest = max(10.0, current_crest * 0.85)  # Slight reduction

        # EQ adjustments based on frequency balance
        eq_adjustments = {
            'sub_bass': self._calculate_eq_adjustment(
                fp_dict.get('sub_bass_pct', freq.get('sub_bass_pct', 5.0)), ideal=5.0
            ),
            'bass': self._calculate_eq_adjustment(
                fp_dict.get('bass_pct', freq.get('bass_pct', 15.0)), ideal=15.0
            ),
            'low_mid': self._calculate_eq_adjustment(
                fp_dict.get('low_mid_pct', freq.get('low_mid_pct', 18.0)), ideal=18.0
            ),
            'mid': self._calculate_eq_adjustment(
                fp_dict.get('mid_pct', freq.get('mid_pct', 22.0)), ideal=22.0
            ),
            'upper_mid': self._calculate_eq_adjustment(
                fp_dict.get('upper_mid_pct', freq.get('upper_mid_pct', 20.0)), ideal=20.0
            ),
            'presence': self._calculate_eq_adjustment(
                fp_dict.get('presence_pct', freq.get('presence_pct', 13.0)), ideal=13.0
            ),
            'air': self._calculate_eq_adjustment(
                fp_dict.get('air_pct', freq.get('air_pct', 7.0)), ideal=7.0
            ),
        }

        return {
            'target_lufs': target_lufs,
            'target_crest_db': target_crest,
            'eq_adjustments_db': eq_adjustments,
            'compression': {
                'ratio': 2.5,
                'amount': 0.6
            }
        }

    def _calculate_eq_adjustment(self, current_pct: float, ideal: float) -> float:
        """
        Calculate EQ adjustment in dB to reach ideal percentage.

        Consolidates logic from chunked_processor._calculate_eq_adjustment().

        Args:
            current_pct: Current frequency percentage
            ideal: Ideal frequency percentage

        Returns:
            EQ adjustment in dB (clamped to ±6 dB)
        """
        # Simple proportional adjustment
        diff = ideal - current_pct
        # ±1% difference = ±0.5 dB adjustment (gentle)
        adjustment = diff * 0.5
        # Clamp to reasonable range
        return max(-6.0, min(6.0, adjustment))

    def clear_cache(self) -> None:
        """Clear all cached fingerprints."""
        with self._lock:
            count = len(self.cache)
            self.cache.clear()
            logger.info(f"Cleared {count} cached fingerprint(s)")


# Global mastering target service instance (singleton pattern)
_global_mastering_target_service: MasteringTargetService | None = None
_service_lock = threading.Lock()


def get_mastering_target_service() -> MasteringTargetService:
    """
    Get global mastering target service instance (singleton).

    Returns:
        Global MasteringTargetService instance
    """
    global _global_mastering_target_service

    if _global_mastering_target_service is None:
        with _service_lock:
            # Double-check locking pattern
            if _global_mastering_target_service is None:
                _global_mastering_target_service = MasteringTargetService()
                logger.info("Global MasteringTargetService instance created")

    return _global_mastering_target_service

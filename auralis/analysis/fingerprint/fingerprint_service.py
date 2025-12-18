# -*- coding: utf-8 -*-

"""
Unified Fingerprinting Service

Consolidates all fingerprinting logic (cache lookup, computation, storage) into
a single interface used by both playback and batch processing.

Replaces:
  - FingerprintGenerator (backend fingerprint_generator.py)
  - MasteringTargetService (backend mastering_target_service.py)
  - Embedded logic in AudioFingerprintAnalyzer usage

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import sqlite3

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage

logger = logging.getLogger(__name__)


class FingerprintService:
    """
    Unified fingerprinting service with 3-tier caching:
    1. Database (SQLite) - fastest, persistent
    2. .25d file cache - fast, portable
    3. On-demand computation - slower but ensures fresh data

    Single interface for all fingerprint operations.
    """

    def __init__(self, db_path: Optional[Path] = None, fingerprint_strategy: str = "sampling"):
        """
        Initialize fingerprinting service.

        Args:
            db_path: Path to SQLite database (default: ~/.auralis/library.db)
            fingerprint_strategy: "sampling" or "full-track" (Phase 7)
        """
        if db_path is None:
            db_path = Path.home() / ".auralis" / "library.db"

        self.db_path = Path(db_path)
        self.fingerprint_strategy = fingerprint_strategy
        self.analyzer = AudioFingerprintAnalyzer(fingerprint_strategy=fingerprint_strategy)

    def get_or_compute(self, audio_path: Path, audio: Optional[np.ndarray] = None, sr: Optional[int] = None) -> Optional[Dict]:
        """
        Get fingerprint using 3-tier cache strategy, or compute new one.

        Args:
            audio_path: Path to audio file
            audio: Optional pre-loaded audio (if None, will load from file)
            sr: Optional sample rate (required if audio provided)

        Returns:
            25D fingerprint dictionary or None on failure

        Priority:
            1. Database cache (SQLite, fastest)
            2. .25d file cache (FingerprintStorage)
            3. On-demand computation (AudioFingerprintAnalyzer)
        """
        try:
            # Tier 1: Check database cache
            fingerprint = self._load_from_database(str(audio_path))
            if fingerprint:
                logger.debug(f"Fingerprint cache hit (database): {audio_path.name}")
                return fingerprint

            # Tier 2: Check .25d file cache
            fingerprint = self._load_from_file_cache(audio_path)
            if fingerprint:
                logger.debug(f"Fingerprint cache hit (.25d file): {audio_path.name}")
                # Save to database for future faster access
                self._save_to_database(str(audio_path), fingerprint)
                return fingerprint

            # Tier 3: Compute new fingerprint
            logger.info(f"Computing fingerprint: {audio_path.name}")
            fingerprint = self._compute_fingerprint(audio_path, audio, sr)

            if fingerprint:
                # Cache to both database and .25d file
                self._save_to_database(str(audio_path), fingerprint)
                FingerprintStorage.save(audio_path, fingerprint, {})
                logger.debug(f"Fingerprint cached for: {audio_path.name}")
                return fingerprint

            return None

        except Exception as e:
            logger.error(f"Fingerprint retrieval failed: {e}")
            return None

    def _load_from_database(self, filepath: str) -> Optional[Dict]:
        """Load fingerprint from SQLite database."""
        try:
            if not self.db_path.exists():
                return None

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Query 25D fingerprint columns
            cursor.execute("""
                SELECT
                    tempo_bpm, lufs, crest_db, bass_pct, mid_pct,
                    harmonic_ratio, transient_density, spectral_centroid,
                    bass_mid_ratio, rhythm_stability, silence_ratio,
                    spectral_rolloff, spectral_flatness, pitch_stability,
                    chroma_energy, dynamic_range_variation, loudness_variation_std,
                    peak_consistency, stereo_width, phase_correlation,
                    sub_bass_pct, low_mid_pct, upper_mid_pct, presence_pct, air_pct
                FROM tracks WHERE filepath = ?
            """, (filepath,))

            row = cursor.fetchone()
            conn.close()

            if not row or row[0] is None:  # Check if tempo_bpm exists
                return None

            # Map columns to fingerprint dict
            return {
                'tempo_bpm': row[0],
                'lufs': row[1],
                'crest_db': row[2],
                'bass_pct': row[3],
                'mid_pct': row[4],
                'harmonic_ratio': row[5],
                'transient_density': row[6],
                'spectral_centroid': row[7],
                'bass_mid_ratio': row[8],
                'rhythm_stability': row[9],
                'silence_ratio': row[10],
                'spectral_rolloff': row[11],
                'spectral_flatness': row[12],
                'pitch_stability': row[13],
                'chroma_energy': row[14],
                'dynamic_range_variation': row[15],
                'loudness_variation_std': row[16],
                'peak_consistency': row[17],
                'stereo_width': row[18],
                'phase_correlation': row[19],
                'sub_bass_pct': row[20],
                'low_mid_pct': row[21],
                'upper_mid_pct': row[22],
                'presence_pct': row[23],
                'air_pct': row[24],
            }

        except Exception as e:
            logger.debug(f"Database fingerprint lookup failed: {e}")
            return None

    def _load_from_file_cache(self, audio_path: Path) -> Optional[Dict]:
        """Load fingerprint from .25d file cache."""
        try:
            cached_data = FingerprintStorage.load(audio_path)
            if cached_data:
                fingerprint, _ = cached_data
                return fingerprint
            return None
        except Exception as e:
            logger.debug(f"File cache lookup failed: {e}")
            return None

    def _compute_fingerprint(
        self,
        audio_path: Path,
        audio: Optional[np.ndarray] = None,
        sr: Optional[int] = None
    ) -> Optional[Dict]:
        """Compute fingerprint using AudioFingerprintAnalyzer."""
        try:
            import librosa

            # Load audio if not provided
            if audio is None or sr is None:
                audio, sr = librosa.load(str(audio_path), sr=None, mono=False)

            # Ensure float64 for PyO3 compatibility
            audio = audio.astype(np.float64)

            # Compute fingerprint
            fingerprint = self.analyzer.analyze(audio, sr)

            # Convert numpy types to JSON-safe Python types
            fingerprint_clean = self._numpy_to_python(fingerprint)

            return fingerprint_clean

        except Exception as e:
            logger.error(f"Fingerprint computation failed: {e}")
            return None

    def _save_to_database(self, filepath: str, fingerprint: Dict) -> bool:
        """Save fingerprint to SQLite database."""
        try:
            if not self.db_path.exists():
                return False

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Update 25D columns
            cursor.execute("""
                UPDATE tracks SET
                    tempo_bpm = ?,
                    lufs = ?,
                    crest_db = ?,
                    bass_pct = ?,
                    mid_pct = ?,
                    harmonic_ratio = ?,
                    transient_density = ?,
                    spectral_centroid = ?,
                    bass_mid_ratio = ?,
                    rhythm_stability = ?,
                    silence_ratio = ?,
                    spectral_rolloff = ?,
                    spectral_flatness = ?,
                    pitch_stability = ?,
                    chroma_energy = ?,
                    dynamic_range_variation = ?,
                    loudness_variation_std = ?,
                    peak_consistency = ?,
                    stereo_width = ?,
                    phase_correlation = ?,
                    sub_bass_pct = ?,
                    low_mid_pct = ?,
                    upper_mid_pct = ?,
                    presence_pct = ?,
                    air_pct = ?
                WHERE filepath = ?
            """, (
                fingerprint.get('tempo_bpm'),
                fingerprint.get('lufs'),
                fingerprint.get('crest_db'),
                fingerprint.get('bass_pct'),
                fingerprint.get('mid_pct'),
                fingerprint.get('harmonic_ratio'),
                fingerprint.get('transient_density'),
                fingerprint.get('spectral_centroid'),
                fingerprint.get('bass_mid_ratio'),
                fingerprint.get('rhythm_stability'),
                fingerprint.get('silence_ratio'),
                fingerprint.get('spectral_rolloff'),
                fingerprint.get('spectral_flatness'),
                fingerprint.get('pitch_stability'),
                fingerprint.get('chroma_energy'),
                fingerprint.get('dynamic_range_variation'),
                fingerprint.get('loudness_variation_std'),
                fingerprint.get('peak_consistency'),
                fingerprint.get('stereo_width'),
                fingerprint.get('phase_correlation'),
                fingerprint.get('sub_bass_pct'),
                fingerprint.get('low_mid_pct'),
                fingerprint.get('upper_mid_pct'),
                fingerprint.get('presence_pct'),
                fingerprint.get('air_pct'),
                filepath
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.debug(f"Database save failed: {e}")
            return False

    @staticmethod
    def _numpy_to_python(obj):
        """Recursively convert NumPy types to native Python types."""
        if isinstance(obj, dict):
            return {k: FingerprintService._numpy_to_python(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return type(obj)(FingerprintService._numpy_to_python(v) for v in obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.floating, np.integer)):
            return float(obj) if isinstance(obj, np.floating) else int(obj)
        elif isinstance(obj, (np.bool_)):
            return bool(obj)
        else:
            return obj

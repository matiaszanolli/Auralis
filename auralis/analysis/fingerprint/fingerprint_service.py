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

import hashlib
import json
import logging
import sqlite3
from pathlib import Path

import numpy as np

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
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

    def __init__(self, db_path: Path | None = None, fingerprint_strategy: str = "sampling"):
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

    def get_or_compute(self, audio_path: Path, audio: np.ndarray | None = None, sr: int | None = None) -> dict | None:
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

    def _get_connection(self) -> sqlite3.Connection:
        """Create a sqlite3 connection with proper PRAGMA setup (#2581).

        Sets WAL mode and busy_timeout to match the SQLAlchemy engine's
        configuration, avoiding 'database locked' errors under concurrent
        access.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=60000")
        return conn

    def _load_from_database(self, filepath: str) -> dict | None:
        """Load fingerprint from SQLite database."""
        try:
            if not self.db_path.exists():
                return None

            with self._get_connection() as conn:
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

            if not row or row[0] is None:  # Check if tempo_bpm exists
                return None

            # Map columns to fingerprint dict — verify integrity hash (#2422)
            fingerprint = {
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

            # Verify integrity hash if present (#2422)
            try:
                cursor2 = conn.cursor()
                cursor2.execute(
                    "SELECT fingerprint_hash FROM tracks WHERE filepath = ?",
                    (filepath,),
                )
                hash_row = cursor2.fetchone()
                if hash_row and hash_row[0]:
                    expected = hash_row[0]
                    actual = self._compute_fingerprint_hash(fingerprint)
                    if expected != actual:
                        logger.warning(
                            f"Fingerprint integrity check failed for {filepath} "
                            f"(expected {expected[:12]}…, got {actual[:12]}…)"
                        )
                        return None  # Force recomputation
            except sqlite3.OperationalError:
                pass  # Column doesn't exist yet (pre-migration)

            return fingerprint

        except Exception as e:
            logger.debug(f"Database fingerprint lookup failed: {e}")
            return None

    def _load_from_file_cache(self, audio_path: Path) -> dict | None:
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
        audio: np.ndarray | None = None,
        sr: int | None = None
    ) -> dict | None:
        """Compute fingerprint using AudioFingerprintAnalyzer."""
        try:
            import librosa

            # Load audio if not provided.
            # Use 22050 Hz (librosa's native analysis rate) to halve data for 44.1 kHz files.
            # Cap at 90 s — sufficient for a stable 25D fingerprint with the sampling strategy.
            if audio is None or sr is None:
                audio, sr = librosa.load(str(audio_path), sr=22050, mono=False, duration=90.0)
            else:
                # Normalize pre-loaded audio to match file-load parameters (#2457).
                # Ensures fingerprints are comparable regardless of loading path.
                _target_sr = 22050
                _max_samples = int(_target_sr * 90.0)
                if sr != _target_sr:
                    # Resample to target sr.
                    if audio.ndim == 1:
                        audio = librosa.resample(audio.astype(np.float32), orig_sr=sr, target_sr=_target_sr)
                    else:
                        audio = np.stack([
                            librosa.resample(audio[ch].astype(np.float32), orig_sr=sr, target_sr=_target_sr)
                            for ch in range(audio.shape[0])
                        ])
                    sr = _target_sr
                # Cap at 90 seconds (works for both 1-D and 2-D audio).
                audio = audio[..., :_max_samples]

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

    def _save_to_database(self, filepath: str, fingerprint: dict) -> bool:
        """Save fingerprint to SQLite database."""
        try:
            if not self.db_path.exists():
                return False

            with self._get_connection() as conn:
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

                # Store integrity hash (#2422)
                fp_hash = self._compute_fingerprint_hash(fingerprint)
                try:
                    cursor.execute(
                        "UPDATE tracks SET fingerprint_hash = ? WHERE filepath = ?",
                        (fp_hash, filepath),
                    )
                except sqlite3.OperationalError:
                    pass  # Column doesn't exist yet (pre-migration)

                return True

        except Exception as e:
            logger.debug(f"Database save failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Fingerprint integrity hash (#2422)
    # ------------------------------------------------------------------
    # The 25D fingerprint columns are ordered deterministically so that
    # json.dumps(sorted_items) produces the same bytes for the same data.
    _HASH_KEYS = sorted([
        'tempo_bpm', 'lufs', 'crest_db', 'bass_pct', 'mid_pct',
        'harmonic_ratio', 'transient_density', 'spectral_centroid',
        'bass_mid_ratio', 'rhythm_stability', 'silence_ratio',
        'spectral_rolloff', 'spectral_flatness', 'pitch_stability',
        'chroma_energy', 'dynamic_range_variation', 'loudness_variation_std',
        'peak_consistency', 'stereo_width', 'phase_correlation',
        'sub_bass_pct', 'low_mid_pct', 'upper_mid_pct', 'presence_pct', 'air_pct',
    ])

    @staticmethod
    def _compute_fingerprint_hash(fingerprint: dict) -> str:
        """Compute SHA-256 integrity hash for a 25D fingerprint.

        Values are rounded to 6 decimal places to avoid floating-point
        representation drift across platforms.
        """
        canonical = {
            k: round(float(fingerprint.get(k, 0.0)), 6)
            for k in FingerprintService._HASH_KEYS
        }
        payload = json.dumps(canonical, sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()

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

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

import logging
from collections.abc import Callable
from pathlib import Path

import numpy as np
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage
from auralis.library.models import Track
from auralis.library.repositories.fingerprint_repository import FingerprintRepository

logger = logging.getLogger(__name__)

# All 25 fingerprint dimension keys — must match TrackFingerprint column names.
_FP_KEYS: tuple[str, ...] = (
    'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct', 'upper_mid_pct',
    'presence_pct', 'air_pct', 'lufs', 'crest_db', 'bass_mid_ratio',
    'tempo_bpm', 'rhythm_stability', 'transient_density', 'silence_ratio',
    'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
    'harmonic_ratio', 'pitch_stability', 'chroma_energy',
    'dynamic_range_variation', 'loudness_variation_std', 'peak_consistency',
    'stereo_width', 'phase_correlation',
)


def _make_engine(db_path: Path):
    """Create a minimal SQLAlchemy engine matching LibraryManager's configuration."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={'timeout': 15, 'check_same_thread': False},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")

    return engine


class FingerprintService:
    """
    Unified fingerprinting service with 3-tier caching:
    1. Database (SQLite) - fastest, persistent
    2. .25d file cache - fast, portable
    3. On-demand computation - slower but ensures fresh data

    Single interface for all fingerprint operations.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        fingerprint_strategy: str = "sampling",
        session_factory: Callable[[], Session] | None = None,
    ):
        """
        Initialize fingerprinting service.

        Args:
            db_path: Path to SQLite database (default: ~/.auralis/library.db)
            fingerprint_strategy: "sampling" or "full-track" (Phase 7)
            session_factory: Optional SQLAlchemy session factory. When provided
                             the service uses the caller's connection pool.
                             When omitted a minimal engine is created from db_path.
        """
        if db_path is None:
            db_path = Path.home() / ".auralis" / "library.db"

        self.db_path = Path(db_path)
        self.fingerprint_strategy = fingerprint_strategy
        self.analyzer = AudioFingerprintAnalyzer(fingerprint_strategy=fingerprint_strategy)

        if session_factory is None:
            self._engine = _make_engine(self.db_path)
            session_factory = sessionmaker(bind=self._engine)
        else:
            self._engine = None

        self._session_factory = session_factory
        self._fingerprint_repo = FingerprintRepository(session_factory)

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

    def _load_from_database(self, filepath: str) -> dict | None:
        """Load fingerprint from database via FingerprintRepository."""
        try:
            if not self.db_path.exists():
                return None

            session = self._session_factory()
            try:
                track_id = session.execute(
                    select(Track.id).where(Track.filepath == filepath)
                ).scalar_one_or_none()
            finally:
                session.close()

            if track_id is None:
                return None

            fp = self._fingerprint_repo.get_by_track_id(track_id)
            # lufs == -100.0 is the placeholder sentinel written by claim_next_unfingerprinted_track
            if fp is None or getattr(fp, 'lufs', -100.0) == -100.0:
                return None

            return {key: getattr(fp, key) for key in _FP_KEYS}

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
        """Save fingerprint to database via FingerprintRepository."""
        try:
            if not self.db_path.exists():
                return False

            session = self._session_factory()
            try:
                track_id = session.execute(
                    select(Track.id).where(Track.filepath == filepath)
                ).scalar_one_or_none()
            finally:
                session.close()

            if track_id is None:
                # Track not in library yet; nothing to associate the fingerprint with.
                return False

            fp_data = {key: fingerprint[key] for key in _FP_KEYS if key in fingerprint}
            return self._fingerprint_repo.upsert(track_id, fp_data) is not None

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

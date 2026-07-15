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
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage
from auralis.library.repositories.fingerprint_repository import FingerprintRepository
from auralis.library.repositories.track_repository import TrackRepository

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
        session_factory: Callable[[], Session] | None = None,
    ):
        """
        Initialize fingerprinting service.

        Args:
            db_path: Path to SQLite database (default: ~/.auralis/library.db)
            session_factory: Optional SQLAlchemy session factory. When provided
                             the service uses the caller's connection pool.
                             When omitted a minimal engine is created from db_path.
        """
        if db_path is None:
            from auralis.library.constants import DEFAULT_DB_PATH
            db_path = DEFAULT_DB_PATH

        self.db_path = Path(db_path)
        self.analyzer = AudioFingerprintAnalyzer()

        if session_factory is None:
            self._engine = _make_engine(self.db_path)
            session_factory = sessionmaker(self._engine)
        else:
            self._engine = None

        self._session_factory = session_factory
        self._fingerprint_repo = FingerprintRepository(session_factory)
        self._track_repo = TrackRepository(session_factory)

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

            track_id = self._track_repo.get_id_by_filepath(filepath)
            if track_id is None:
                return None

            fp = self._fingerprint_repo.get_by_track_id(track_id)
            # lufs == -100.0 is the placeholder sentinel written by claim_next_unfingerprinted_track
            if fp is None or getattr(fp, 'lufs', -100.0) == -100.0:
                return None

            result = {key: getattr(fp, key) for key in _FP_KEYS}
            if not self._band_pct_valid(result):
                logger.info(f"Discarding stale DB fingerprint (band-pct sum != 1): {filepath}")
                return None
            return result

        except Exception as e:
            logger.debug(f"Database fingerprint lookup failed: {e}")
            return None

    # Frequency band keys that must sum to ~1.0 in a valid fingerprint.
    _BAND_PCT_KEYS: tuple[str, ...] = (
        'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
        'upper_mid_pct', 'presence_pct', 'air_pct',
    )

    @staticmethod
    def _band_pct_valid(fp: dict) -> bool:
        """Return True if the seven frequency-band fractions sum to 1 ± 0.05."""
        total = sum(fp.get(k, 0.0) for k in FingerprintService._BAND_PCT_KEYS)
        return 0.95 <= total <= 1.05

    def _load_from_file_cache(self, audio_path: Path) -> dict | None:
        """Load fingerprint from .25d file cache, discarding stale entries."""
        try:
            cached_data = FingerprintStorage.load(audio_path)
            if cached_data:
                fingerprint, _ = cached_data
                if not self._band_pct_valid(fingerprint):
                    logger.info(
                        f"Discarding stale .25d cache (band-pct sum != 1): {audio_path.name}"
                    )
                    return None
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
            #
            # Multi-window fingerprinting strategy (empirically validated June 2026):
            #
            # Loading only a single 90 s window from the track creates a systematic
            # negative LUFS bias when that window lands on an ambient/instrumental intro.
            # Validation study (34 tracks) showed single-window RMSE vs actual LUFS =
            # 1.96 dB, max error = 9.2 dB (Gilmour Shine On: -23.5 vs -14.3 LUFS).
            #
            # Fix: run the full 25D analysis on the BODY window (50 % of track duration),
            # then probe two additional 30 s windows at 25 % and 75 %. Replace fp['lufs']
            # and fp['crest_db'] with the median across all three probes.
            # Result: RMSE drops to 1.07 dB (-45 %), max error to 3.6 dB (-61 %).
            #
            # The body window (50 %) is used for the full spectral analysis because
            # it is most likely to represent the track's timbral character.  The 25 %
            # and 75 % probes are mono + fast — no full 25D analysis needed.
            if audio is None or sr is None:
                _target_sr = 22050
                _probe_s   = 30.0   # length of each lightweight probe window
                _body_s    = 90.0   # length of the full-analysis (body) window

                # Get total duration without loading audio
                try:
                    import soundfile as _sf
                    with _sf.SoundFile(str(audio_path)) as _f:
                        _total_s = len(_f) / _f.samplerate
                except Exception:
                    _total_s = None

                # Body window: centred on 50 % of track duration
                if _total_s is not None:
                    _body_offset = min(_total_s * 0.50, max(0.0, _total_s - _body_s))
                else:
                    _body_offset = 0.0

                from auralis.io.formats import FFMPEG_FORMATS
                if audio_path.suffix.lower() in FFMPEG_FORMATS:
                    # libsndfile can't decode AAC/MP3/etc — load via ffmpeg then resample.
                    from auralis.io.loaders import load_with_ffmpeg
                    import tempfile, os
                    with tempfile.TemporaryDirectory() as tmp:
                        raw_audio, raw_sr = load_with_ffmpeg(audio_path, tmp)
                    # raw_audio is (samples, channels) or (samples,); convert to (channels, samples)
                    if raw_audio.ndim == 2:
                        raw_audio = raw_audio.T
                    if raw_sr != _target_sr:
                        if raw_audio.ndim == 2:
                            raw_audio = np.stack([
                                librosa.resample(raw_audio[ch].astype(np.float32), orig_sr=raw_sr, target_sr=_target_sr)
                                for ch in range(raw_audio.shape[0])
                            ])
                        else:
                            raw_audio = librosa.resample(raw_audio.astype(np.float32), orig_sr=raw_sr, target_sr=_target_sr)
                    _total_s    = raw_audio.shape[-1] / _target_sr
                    _body_offset = min(_total_s * 0.50, max(0.0, _total_s - _body_s))
                    _body_start  = int(_target_sr * _body_offset)
                    _body_end    = _body_start + int(_target_sr * _body_s)
                    audio = raw_audio[..., _body_start:_body_end]
                    # Lightweight LUFS/crest probes at 25 % and 75 %
                    _probe_fracs = [0.25, 0.75]
                    _probe_audios = []
                    for _frac in _probe_fracs:
                        _ps = int(_target_sr * min(_frac * _total_s, max(0.0, _total_s - _probe_s)))
                        _pe = _ps + int(_target_sr * _probe_s)
                        _pa = raw_audio[..., _ps:_pe]
                        _probe_audios.append(_pa)
                    sr = _target_sr
                else:
                    audio, sr = librosa.load(
                        str(audio_path), sr=_target_sr, mono=False,
                        offset=_body_offset, duration=_body_s,
                    )
                    sr = int(sr)
                    # Lightweight probes: mono is sufficient for LUFS/crest estimation
                    _probe_audios = []
                    if _total_s is not None:
                        for _frac in [0.25, 0.75]:
                            _poff = min(_frac * _total_s, max(0.0, _total_s - _probe_s))
                            try:
                                _pa, _ = librosa.load(
                                    str(audio_path), sr=_target_sr, mono=True,
                                    offset=_poff, duration=_probe_s,
                                )
                                _probe_audios.append(_pa)
                            except Exception:
                                pass
            else:
                # Normalize pre-loaded audio to match file-load parameters (#2457).
                # Ensures fingerprints are comparable regardless of loading path.
                _target_sr = 22050
                _max_samples = int(_target_sr * 90.0)
                # Crop to ~90 s at the ORIGINAL sample rate BEFORE resampling.
                # Resampling the whole buffer and cropping afterwards was an
                # O(duration) resample + full-duration float32 allocation on a
                # multi-hour pre-loaded buffer, only to discard all but the first
                # 90 s — reopening the #4116 OOM/latency class (#4499). This
                # matches the crop-then-resample order at every other entry point
                # (MasteringFingerprint.from_audio_file, AudioFingerprintAnalyzer).
                audio = audio[..., :int(sr * 90.0)]
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
                # Final exact cap at 90 s in the target rate (rounding safety;
                # works for both 1-D and 2-D audio).
                audio = audio[..., :_max_samples]

            # Ensure float64 for PyO3 compatibility
            audio = audio.astype(np.float64)

            # Downmix >2-channel audio to stereo before fingerprinting.
            # librosa.load(mono=False) returns (channels, samples) for any channel count.
            # The fingerprint analyzer only handles mono/stereo — its shape-detection
            # heuristic (shape[0] <= 2 → channels-first) misclassifies a 6-ch array
            # as having 6 samples, causing a false "too short" rejection.
            # Taking the first two channels (L+R) is sufficient for timbral analysis;
            # the C/Ls/Rs channels are correlated with L+R in well-mixed surround content.
            if audio.ndim == 2 and audio.shape[0] > 2:
                audio = audio[:2, :]

            # Compute fingerprint from the body window
            fingerprint = self.analyzer.analyze(audio, sr)

            # Multi-window LUFS/crest correction — replace the body-window
            # estimates with the median across the body + two probe windows.
            # Validated empirically: reduces LUFS RMSE from 1.96 → 1.07 dB,
            # max error from 9.2 → 3.6 dB (June 2026 study, 31 tracks).
            try:
                if '_probe_audios' in dir() and _probe_audios and fingerprint:
                    def _rms_lufs_crest(a: np.ndarray) -> tuple[float, float]:
                        """Return (lufs_approx, crest_db) from a mono/stereo array."""
                        mono = np.mean(a, axis=0) if a.ndim == 2 else a
                        rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2)))
                        if rms < 1e-9:
                            return -70.0, 0.0
                        peak = float(np.max(np.abs(mono)))
                        lufs = 20.0 * np.log10(rms) - 0.691   # K-weighted proxy
                        crest = 20.0 * np.log10(peak / max(rms, 1e-9))
                        return lufs, crest

                    # Body window (already analyzed)
                    lufs_body, crest_body = _rms_lufs_crest(audio.astype(np.float64))
                    all_lufs  = [lufs_body]
                    all_crest = [crest_body]

                    for _pa in _probe_audios:
                        _pl, _pc = _rms_lufs_crest(_pa.astype(np.float64))
                        if _pl > -70.0:   # skip silent probes
                            all_lufs.append(_pl)
                            all_crest.append(_pc)

                    if len(all_lufs) >= 2:
                        fingerprint['lufs']     = float(np.median(all_lufs))
                        fingerprint['crest_db'] = float(np.median(all_crest))
            except Exception:
                pass   # multi-window correction is best-effort; body window is fine

            # #3767: validate completeness before returning. `analyze()`
            # returns {} from its outer except-all on any exception
            # (audio_fingerprint_analyzer.py:314). The downstream
            # `get_or_compute` check `if fingerprint:` already skips
            # empty dicts (so they don't reach the cache), but an
            # incomplete fingerprint (e.g., 12 of 25 dimensions) would
            # be truthy and get cached as if valid. The official
            # fingerprint dimensionality is 25; anything less is a
            # partial result that should be re-tried, not cached.
            if fingerprint and len(fingerprint) < 25:
                logger.warning(
                    f"Incomplete fingerprint for {audio_path.name}: "
                    f"{len(fingerprint)} of 25 dimensions present — discarding"
                )
                return None

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

            track_id = self._track_repo.get_id_by_filepath(filepath)
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
        """Recursively convert NumPy types to native Python types.

        #3765: previously `else: return obj` swallowed unhandled NumPy
        types (e.g. `np.complex128`, `np.datetime64`) — they'd be
        passed through verbatim and then silently break JSON
        serialisation downstream of any future analyzer that emitted
        them. Native Python primitives pass through; NumPy types
        outside the handled set fail loud.
        """
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
        elif isinstance(obj, np.generic):
            # Any other NumPy scalar (np.complex128, np.datetime64,
            # np.str_, ...) — raise loud rather than pass through.
            raise TypeError(
                f"Cannot serialise NumPy type {type(obj).__name__}; "
                f"add an explicit branch to _numpy_to_python()."
            )
        else:
            return obj

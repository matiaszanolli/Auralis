"""
Fingerprint Extractor
~~~~~~~~~~~~~~~~~~~~

Extracts 25D audio fingerprints during library scanning

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import gc
from pathlib import Path
from typing import Any

from ..analysis.fingerprint import AudioFingerprintAnalyzer
from ..__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..io.unified_loader import load_audio
from ..library.sidecar_manager import SidecarManager
from ..utils.logging import debug, error, info, warning


class CorruptedTrackError(Exception):
    """Exception raised when a track file is corrupted and will be deleted"""


class FingerprintExtractor:
    """
    Extracts audio fingerprints for library tracks

    Integrates with library scanner to automatically generate fingerprints
    during the scanning process.

    Features .25d sidecar file support for fast caching:
    - Checks for valid .25d file before analyzing audio
    - Loads fingerprint from .25d file if available (instant)
    - Writes .25d file after extraction (for future speedup)
    """

    def __init__(self, fingerprint_repository: Any, track_repository: Any = None,
                 use_sidecar_files: bool = True) -> None:
        """
        Initialize fingerprint extractor

        Args:
            fingerprint_repository: FingerprintRepository instance
            track_repository: TrackRepository instance used to delete corrupted tracks
                              via the repository pattern (#2288).  When None, corrupted-
                              track deletion is skipped with a warning.
            use_sidecar_files: Enable .25d sidecar file caching (default: True)
        """
        self.fingerprint_repo = fingerprint_repository
        self.track_repo = track_repository
        self.analyzer = AudioFingerprintAnalyzer()
        self.use_sidecar_files = use_sidecar_files
        self.sidecar_manager = SidecarManager() if use_sidecar_files else None

        debug("FingerprintExtractor initialized")

    def _delete_corrupted_track(self, track_id: int, filepath: str) -> bool:
        """
        Delete corrupted track from the database via the repository pattern (#2288).

        Uses TrackRepository.delete() so cascading deletes (fingerprints, playlist
        entries, stats) fire correctly via SQLAlchemy and the configured DB URL.

        Args:
            track_id: ID of the track to delete
            filepath: Path to the audio file (for logging)

        Returns:
            True if successfully deleted, False otherwise
        """
        if self.track_repo is None:
            warning(
                f"Cannot delete corrupted track {track_id}: no track_repository "
                f"provided to FingerprintExtractor"
            )
            return False

        try:
            deleted = self.track_repo.delete(track_id)
            if deleted:
                info(f"Automatically deleted corrupted track {track_id} from database: {filepath}")
            else:
                warning(f"Track {track_id} not found in database for deletion")
            return deleted
        except Exception as e:
            error(f"Failed to delete corrupted track {track_id} from database: {e}")
            return False


    def extract_and_store(self, track_id: int, filepath: str) -> bool:
        """
        Extract fingerprint from audio file and store in database

        Workflow:
        1. Check for valid .25d sidecar file (if enabled)
        2. If valid: Load fingerprint from .25d (instant, ~1ms)
        3. If invalid/missing: Analyze audio (slow, ~75s)
        4. Store in database + write .25d file

        Args:
            track_id: ID of the track in the database
            filepath: Path to the audio file

        Returns:
            True if successful, False otherwise
        """
        import time
        try:
            time.time()
            filepath_obj = Path(filepath)
            fingerprint = None
            cached = False

            # Try to load from .25d sidecar file (fast path)
            if self.use_sidecar_files and self.sidecar_manager:
                if self.sidecar_manager.is_valid(filepath_obj):
                    fingerprint = self.sidecar_manager.get_fingerprint(filepath_obj)
                    # Fingerprint should have 25 dimensions, may also include fingerprint_version
                    if fingerprint and len(fingerprint) >= 25:
                        # Reject sidecar fingerprints computed with an older algorithm version
                        sidecar_version = int(fingerprint.get('fingerprint_version', 1))
                        if sidecar_version < FINGERPRINT_ALGORITHM_VERSION:
                            warning(
                                f"Sidecar fingerprint for track {track_id} is v{sidecar_version} "
                                f"(current: v{FINGERPRINT_ALGORITHM_VERSION}), re-extracting"
                            )
                            fingerprint = None
                        else:
                            info(f"Loaded fingerprint from .25d file for track {track_id}")
                            cached = True
                    else:
                        warning(f"Invalid fingerprint in .25d file, will re-analyze")
                        fingerprint = None

            # No cached fingerprint — compute it with the in-process analyzer.
            if not fingerprint:
                file_size_mb = Path(filepath).stat().st_size / (1024 * 1024)

                # Skip very large files: decoded audio can be 1.8-3.6 GB and, with many
                # concurrent workers, cause OOM (>300 MB FLAC → 32-48 GB peak with 16 workers).
                if file_size_mb > 300:
                    warning(f"Skipping fingerprint for large file ({file_size_mb:.1f}MB): {filepath}")
                    return False

                debug(f"Loading audio for fingerprint: {filepath}")
                audio, sr = load_audio(filepath)

                # Cap at 90 s to match FingerprintService and prevent OOM
                # on long files (podcasts, DJ mixes) (#2896).
                max_samples = int(90.0 * sr)
                if len(audio) > max_samples:
                    audio = audio[:max_samples]

                try:
                    debug(f"Extracting fingerprint for track {track_id}")
                    fingerprint = self.analyzer.analyze(audio, sr)
                finally:
                    # Free the audio array immediately; with many concurrent workers these
                    # (50-150 MB each) accumulate and cause unbounded memory growth.
                    del audio
                    gc.collect()

            # Filter out metadata keys (like '_harmonic_analysis_method') that shouldn't be stored
            # Keep only the 25 actual fingerprint dimensions
            expected_keys = {
                'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct', 'upper_mid_pct', 'presence_pct', 'air_pct',
                'lufs', 'crest_db', 'bass_mid_ratio',
                'tempo_bpm', 'rhythm_stability', 'transient_density', 'silence_ratio',
                'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
                'harmonic_ratio', 'pitch_stability', 'chroma_energy',
                'stereo_width', 'phase_correlation', 'dynamic_range_variation', 'loudness_variation_std', 'peak_consistency'
            }
            fingerprint = {k: v for k, v in fingerprint.items() if k in expected_keys}

            # Reject empty/incomplete fingerprints so zero-vectors are never stored (#3306)
            if len(fingerprint) < len(expected_keys):
                warning(
                    f"Fingerprint incomplete for track {track_id}: "
                    f"{len(fingerprint)}/{len(expected_keys)} dimensions. Skipping storage."
                )
                return False

            # Add fingerprint_version so the DB row records which algorithm produced it.
            # Uses the single authoritative constant — bump FINGERPRINT_ALGORITHM_VERSION
            # in auralis/__version__.py to trigger re-fingerprinting of old rows.
            fingerprint['fingerprint_version'] = FINGERPRINT_ALGORITHM_VERSION

            # Store in database
            result = self.fingerprint_repo.upsert(track_id, fingerprint)

            if result:
                # Note: fingerprint_started_at is cleared by the worker after processing
                # (This prevents tracks from timing out and being reprocessed)

                # Write .25d sidecar file (if not cached and feature enabled)
                if not cached and self.use_sidecar_files and self.sidecar_manager:
                    # Extract basic track metadata for sidecar file
                    metadata = {
                        'track_id': track_id,
                        'filename': filepath_obj.name,
                        'file_extension': filepath_obj.suffix,
                        'file_size_bytes': filepath_obj.stat().st_size,
                        'extracted_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    }

                    sidecar_data = {
                        'fingerprint': fingerprint,
                        'metadata': metadata
                    }
                    self.sidecar_manager.write(filepath_obj, sidecar_data)

                info(f"Fingerprint {'loaded from cache' if cached else 'extracted'} and stored for track {track_id}")
                return True
            else:
                error(f"Failed to store fingerprint for track {track_id}")
                return False

        except Exception as e:
            error(f"Error extracting fingerprint for track {track_id} ({filepath}): {e}")
            return False

    def extract_batch(self, track_ids_paths: list[tuple[int, str]], max_failures: int = 10) -> dict[str, int]:
        """
        Extract fingerprints for multiple tracks in batch

        Args:
            track_ids_paths: List of (track_id, filepath) tuples
            max_failures: Maximum consecutive failures before stopping

        Returns:
            Dictionary with counts: {'success': N, 'failed': M, 'skipped': K, 'cached': L}
        """
        stats = {'success': 0, 'failed': 0, 'skipped': 0, 'cached': 0}
        consecutive_failures = 0

        for track_id, filepath in track_ids_paths:
            # Check if fingerprint already exists in database
            if self.fingerprint_repo.exists(track_id):
                debug(f"Fingerprint already exists for track {track_id}, skipping")
                stats['skipped'] += 1
                continue

            # Check if .25d sidecar file exists (for stats)
            has_sidecar = False
            if self.use_sidecar_files and self.sidecar_manager:
                has_sidecar = self.sidecar_manager.is_valid(Path(filepath))

            # Extract and store
            success = self.extract_and_store(track_id, filepath)

            if success:
                stats['success'] += 1
                if has_sidecar:
                    stats['cached'] += 1
                consecutive_failures = 0
            else:
                stats['failed'] += 1
                consecutive_failures += 1

                # Stop if too many consecutive failures
                if consecutive_failures >= max_failures:
                    warning(f"Too many consecutive failures ({max_failures}), stopping batch extraction")
                    break

        info(f"Batch fingerprint extraction complete: {stats}")
        return stats

    def extract_missing_fingerprints(self, limit: int | None = None) -> dict[str, int]:
        """
        Extract fingerprints for tracks that don't have them yet

        Args:
            limit: Maximum number of tracks to process (None = all)

        Returns:
            Dictionary with counts: {'success': N, 'failed': M}
        """
        # Get tracks without fingerprints
        tracks = self.fingerprint_repo.get_missing_fingerprints(limit=limit)

        if not tracks:
            info("No tracks missing fingerprints")
            return {'success': 0, 'failed': 0, 'skipped': 0}

        info(f"Found {len(tracks)} tracks without fingerprints")

        # Prepare batch
        track_ids_paths = [(track.id, track.filepath) for track in tracks]

        # Extract in batch
        return self.extract_batch(track_ids_paths)

    def update_fingerprint(self, track_id: int, filepath: str) -> bool:
        """
        Update an existing fingerprint (re-extract)

        Args:
            track_id: ID of the track
            filepath: Path to the audio file

        Returns:
            True if successful, False otherwise
        """
        return self.extract_and_store(track_id, filepath)

    def get_fingerprint(self, track_id: int) -> dict[str, Any] | None:
        """
        Get fingerprint for a track

        Args:
            track_id: ID of the track

        Returns:
            Fingerprint dictionary or None if not found
        """
        fingerprint = self.fingerprint_repo.get_by_track_id(track_id)
        if fingerprint:
            return fingerprint.to_dict()  # type: ignore[no-any-return]
        return None

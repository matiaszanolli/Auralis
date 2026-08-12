"""
Fingerprint Extractor
~~~~~~~~~~~~~~~~~~~~

Extracts 25D audio fingerprints during library scanning

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import gc
import time
from pathlib import Path
from typing import Any

from ..analysis.fingerprint import AudioFingerprintAnalyzer
from ..analysis.fingerprint.metrics.constants import FINGERPRINT_DIMENSION_NAMES
from ..analysis.fingerprint.windowed_compute import compute_windowed_fingerprint
from ..__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..library.sidecar_manager import SidecarManager
from ..utils.logging import debug, error, info, warning


# Decoded audio can reach 1.8-3.6 GB; with many concurrent workers a >300 MB
# FLAC drives 32-48 GB peak across 16 workers, so oversized files are skipped
# rather than fingerprinted (#2896).
MAX_FINGERPRINT_FILE_SIZE_MB = 300.0


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
            # bool(): track_repo is an untyped `Any`, so its return would
            # otherwise leak Any out of a `-> bool` signature.
            deleted = bool(self.track_repo.delete(track_id))
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
        try:
            filepath_obj = Path(filepath)

            # Strategy 1: the .25d sidecar (fast path, ~1 ms).
            fingerprint = self._load_sidecar_fingerprint(track_id, filepath_obj)
            cached = fingerprint is not None

            # Strategy 2: analyse the audio (slow path, ~75 s).
            if fingerprint is None:
                fingerprint = self._compute_fingerprint(track_id, filepath_obj)

            if fingerprint is None:
                return False

            fingerprint = self._prepare_for_storage(track_id, fingerprint)
            if fingerprint is None:
                return False

            if not self.fingerprint_repo.upsert(track_id, fingerprint):
                error(f"Failed to store fingerprint for track {track_id}")
                return False

            # Note: fingerprint_started_at is cleared by the worker after processing
            # (This prevents tracks from timing out and being reprocessed)
            if not cached:
                self._write_sidecar(track_id, filepath_obj, fingerprint)

            info(
                f"Fingerprint {'loaded from cache' if cached else 'extracted'} "
                f"and stored for track {track_id}"
            )
            return True

        except Exception as e:
            error(f"Error extracting fingerprint for track {track_id} ({filepath}): {e}")
            return False

    def _load_sidecar_fingerprint(self, track_id: int, filepath_obj: Path) -> dict[str, Any] | None:
        """Load a usable fingerprint from the track's .25d sidecar, if any.

        Returns None whenever the sidecar cannot be trusted — feature disabled,
        missing/stale file, too few dimensions, or computed by an older
        algorithm version — which routes the caller to a fresh analysis.
        """
        if not (self.use_sidecar_files and self.sidecar_manager):
            return None
        if not self.sidecar_manager.is_valid(filepath_obj):
            return None

        fingerprint = self.sidecar_manager.get_fingerprint(filepath_obj)
        # A sidecar fingerprint carries the 25 dimensions and may also carry
        # fingerprint_version, hence >= rather than ==.
        if not fingerprint or len(fingerprint) < len(FINGERPRINT_DIMENSION_NAMES):
            warning("Invalid fingerprint in .25d file, will re-analyze")
            return None

        # Reject sidecar fingerprints computed with an older algorithm version.
        sidecar_version = int(fingerprint.get('fingerprint_version', 1))
        if sidecar_version < FINGERPRINT_ALGORITHM_VERSION:
            warning(
                f"Sidecar fingerprint for track {track_id} is v{sidecar_version} "
                f"(current: v{FINGERPRINT_ALGORITHM_VERSION}), re-extracting"
            )
            return None

        info(f"Loaded fingerprint from .25d file for track {track_id}")
        return fingerprint

    def _compute_fingerprint(self, track_id: int, filepath_obj: Path) -> dict[str, Any] | None:
        """Analyse the audio file with the in-process windowed analyzer.

        Returns None if the file is too large to analyse safely, or if the
        analyzer could not produce a fingerprint.
        """
        file_size_mb = filepath_obj.stat().st_size / (1024 * 1024)
        if file_size_mb > MAX_FINGERPRINT_FILE_SIZE_MB:
            warning(
                f"Skipping fingerprint for large file ({file_size_mb:.1f}MB): {filepath_obj}"
            )
            return None

        # #4595: use the SINGLE shared windowing implementation rather
        # than a local load + first-90s crop + single-window analyze.
        # This path previously truncated to the first 90 s from the
        # START, which systematically under-reads LUFS when a track
        # opens on an ambient intro (validated: RMSE 1.96 dB, max
        # 9.2 dB vs 1.07 / 3.6 for the body+probe strategy). Because
        # the background queue almost always wins the race to write the
        # DB row, essentially every scanned track was stamped with the
        # less accurate fingerprint and never recomputed.
        #
        # compute_windowed_fingerprint() does its own bounded loading
        # (body window + two 30 s probes at the analysis rate), so it
        # never materialises the whole decoded file — which also
        # preserves the #2896 OOM protection the size guard above provides.
        try:
            debug(f"Extracting fingerprint for track {track_id}")
            fingerprint = compute_windowed_fingerprint(self.analyzer, filepath_obj)
        finally:
            # Release any large intermediates promptly; with many
            # concurrent workers these accumulate and cause unbounded
            # memory growth.
            gc.collect()

        # compute_windowed_fingerprint() returns None on any failure, where the
        # previous analyzer.analyze() call always returned a dict (possibly {}).
        # Guard explicitly so the caller's .items() filter cannot raise (#4595).
        if not fingerprint:
            warning(f"Fingerprint computation returned nothing for track {track_id}")
            return None
        return fingerprint

    def _prepare_for_storage(
        self, track_id: int, fingerprint: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Strip metadata keys, reject incomplete vectors, stamp the version.

        Returns None when the fingerprint is missing dimensions, so a partial
        vector is never stored as if it were complete (#3306).
        """
        stored = {k: v for k, v in fingerprint.items() if k in FINGERPRINT_DIMENSION_NAMES}

        if len(stored) < len(FINGERPRINT_DIMENSION_NAMES):
            warning(
                f"Fingerprint incomplete for track {track_id}: "
                f"{len(stored)}/{len(FINGERPRINT_DIMENSION_NAMES)} dimensions. Skipping storage."
            )
            return None

        # Record which algorithm produced this row. Uses the single authoritative
        # constant — bump FINGERPRINT_ALGORITHM_VERSION in auralis/__version__.py
        # to trigger re-fingerprinting of old rows.
        stored['fingerprint_version'] = FINGERPRINT_ALGORITHM_VERSION
        return stored

    def _write_sidecar(
        self, track_id: int, filepath_obj: Path, fingerprint: dict[str, Any]
    ) -> None:
        """Write the freshly computed fingerprint out as a .25d sidecar."""
        if not (self.use_sidecar_files and self.sidecar_manager):
            return

        self.sidecar_manager.write(filepath_obj, {
            'fingerprint': fingerprint,
            'metadata': {
                'track_id': track_id,
                'filename': filepath_obj.name,
                'file_extension': filepath_obj.suffix,
                'file_size_bytes': filepath_obj.stat().st_size,
                'extracted_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            },
        })

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

"""
Fingerprint Extractor
~~~~~~~~~~~~~~~~~~~~

Extracts 25D audio fingerprints during library scanning

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
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

    def __init__(self, fingerprint_repository: Any, use_sidecar_files: bool = True) -> None:
        """
        Initialize fingerprint extractor

        Args:
            fingerprint_repository: FingerprintRepository instance
            use_sidecar_files: Enable .25d sidecar file caching (default: True)
        """
        self.fingerprint_repo = fingerprint_repository
        self.analyzer = AudioFingerprintAnalyzer()
        self.use_sidecar_files = use_sidecar_files
        self.sidecar_manager = SidecarManager() if use_sidecar_files else None

        debug("FingerprintExtractor initialized")


    def extract_and_store(self, track_id: int, filepath: str) -> bool:
        """
        Extract fingerprint from audio file and store in database

        Workflow:
        1. Check for valid .25d sidecar file (if enabled)
        2. If valid: Load fingerprint from .25d (instant, ~1ms)
        3. If invalid/missing: Analyze audio (~1 s of DSP on a release build,
           plus decode; #4599 re-measured this)
        4. Store in database + write .25d file

        The "~75 s" this used to claim predated #4599, when estimate_tempo ran a
        naive O(bins x N) DFT per frame. Measured on a 90 s buffer (the crop
        this path applies): 9.5 s -> 0.6 s per track on a release build. A
        `maturin develop` debug build is ~25x slower again, which is the most
        likely origin of the original figure — quote release numbers here.

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

            # Strategy 2: analyse the audio (slow path: decode + ~1 s of DSP
            # on a release build — see the workflow note above, #4599).
            if fingerprint is None:
                fingerprint = self._compute_fingerprint(track_id, filepath_obj)

            if fingerprint is None:
                return False

            fingerprint = self._prepare_for_storage(track_id, fingerprint)
            if fingerprint is None:
                return False

            if not self.fingerprint_repo.upsert(track_id, fingerprint, expected_filepath=filepath):
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
        try:
            sidecar_version = int(fingerprint.get('fingerprint_version', 1))
        except (TypeError, ValueError):
            warning("Sidecar fingerprint_version is not a number, will re-analyze")
            return None
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

        Returns None if the analyzer could not produce a fingerprint.
        """
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
        # never materialises the whole decoded file, so memory does not scale
        # with file size and no size guard is needed (a hi-res or hours-long
        # file is fingerprinted like any other, #6145).
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

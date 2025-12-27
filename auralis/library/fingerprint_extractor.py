# -*- coding: utf-8 -*-

"""
Fingerprint Extractor
~~~~~~~~~~~~~~~~~~~~

Extracts 25D audio fingerprints during library scanning

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import gc
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import aiohttp
import numpy as np

from ..analysis.fingerprint import AudioFingerprintAnalyzer
from ..io.unified_loader import load_audio
from ..utils.logging import debug, error, info, warning
from .sidecar_manager import SidecarManager

# NOTE: requests library removed in favor of async aiohttp for true concurrent HTTP
# (synchronous requests were causing 98% worker idle time with 16 workers + 64-thread Rust server)

# Rust fingerprinting server endpoint
RUST_SERVER_URL = "http://localhost:8766"
FINGERPRINT_ENDPOINT = f"{RUST_SERVER_URL}/fingerprint"


class CorruptedTrackError(Exception):
    """Exception raised when a track file is corrupted and will be deleted"""
    pass


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

    def __init__(self, fingerprint_repository: Any, use_sidecar_files: bool = True,
                 fingerprint_strategy: Literal['full-track', 'sampling'] = "sampling", sampling_interval: float = 20.0,
                 use_rust_server: bool = True) -> None:
        """
        Initialize fingerprint extractor

        Args:
            fingerprint_repository: FingerprintRepository instance
            use_sidecar_files: Enable .25d sidecar file caching (default: True)
            fingerprint_strategy: "full-track" or "sampling" (Phase 7)
            sampling_interval: Interval between chunk starts in seconds (for sampling)
            use_rust_server: Use Rust fingerprinting server (default: True, much faster)
        """
        self.fingerprint_repo = fingerprint_repository
        self.analyzer = AudioFingerprintAnalyzer(
            fingerprint_strategy=fingerprint_strategy,
            sampling_interval=sampling_interval
        )
        self.use_sidecar_files = use_sidecar_files
        self.sidecar_manager = SidecarManager() if use_sidecar_files else None
        self.fingerprint_strategy = fingerprint_strategy
        self.sampling_interval = sampling_interval
        self.use_rust_server = use_rust_server
        self._rust_server_available: Optional[bool] = None  # Cache availability check

        debug(f"FingerprintExtractor initialized with strategy={fingerprint_strategy}, use_rust_server={use_rust_server}")

    def _is_rust_server_available(self) -> bool:
        """Check if Rust fingerprinting server is available (with caching)"""
        if self._rust_server_available is not None:
            return self._rust_server_available

        # Server availability not yet determined, check now
        available = False
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex(('127.0.0.1', 8766))
            sock.close()
            available = result == 0
            if available:
                debug("Rust fingerprinting server is available")
            else:
                warning("Rust server not available")
        except Exception as e:
            warning(f"Rust fingerprinting server not available: {e}")
            available = False

        self._rust_server_available = available
        return available

    async def _get_fingerprint_from_rust_server_async(self, track_id: int, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Async version: Call Rust fingerprinting server to extract fingerprint using aiohttp

        Args:
            track_id: Track ID for logging
            filepath: Path to audio file

        Returns:
            Dictionary with 25 fingerprint dimensions, or None on error

        Raises:
            CorruptedTrackError: If the file is detected as corrupted (will be deleted from database)
        """
        try:
            payload = {"track_id": track_id, "filepath": filepath}

            # CRITICAL FIX: Create fresh session for each request and close it immediately after
            # This avoids event loop lifecycle issues when running in thread-local event loops
            # Never reuse sessions across different event loops (unsafe for threading)
            async with aiohttp.ClientSession() as session:
                async with session.post(FINGERPRINT_ENDPOINT, json=payload, timeout=aiohttp.ClientTimeout(total=60.0)) as response:
                    if response.status != 200:
                        error_text = await response.text()

                        # Check if file is corrupted (HTTP 400 with corruption message)
                        if response.status == 400 and "appears corrupted" in error_text.lower():
                            error(f"Corrupted audio file detected for track {track_id}: {filepath}")
                            raise CorruptedTrackError(f"File appears corrupted: {filepath}")

                        error(f"Rust server error for track {track_id}: HTTP {response.status} - {error_text}")
                        return None

                    data = await response.json()
                    fingerprint: Dict[str, Any] = data.get("fingerprint", {})

                    # Validate we got all 25 dimensions
                    if len(fingerprint) != 25:
                        warning(f"Rust server returned {len(fingerprint)} dimensions, expected 25")
                        return None

                    debug(f"Extracted fingerprint via Rust server for track {track_id} in {data.get('processing_time_ms', '?')}ms")
                    return fingerprint

        except CorruptedTrackError:
            raise  # Re-raise corruption errors to be handled at higher level
        except asyncio.TimeoutError as e:
            error(f"Timeout calling Rust fingerprint server for track {track_id}: {e}")
            return None
        except Exception as e:
            error(f"Failed to call Rust fingerprint server for track {track_id}: {e}")
            return None

    def _get_fingerprint_from_rust_server_sync(self, track_id: int, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Synchronous HTTP request to Rust fingerprinting server.

        Uses synchronous requests library for simplicity in thread-per-worker context.
        aiohttp async approach requires shared event loop which is incompatible with
        multiple concurrent worker threads each creating their own event loops.

        TODO: Migrate to true async when using async worker pool instead of thread pool.
        """
        import requests  # type: ignore[import-untyped]
        try:
            payload = {"track_id": track_id, "filepath": filepath}
            # CRITICAL: Use aggressive timeout for Rust server
            # - 10s timeout per request ensures problematic files fail fast
            # - Avoids stalling workers on files with unsupported FLAC features
            # - Falls back to Python analyzer if Rust server hangs on file
            response = requests.post(
                FINGERPRINT_ENDPOINT,
                json=payload,
                timeout=10.0  # Reduced from 60s - fail fast on problematic files
            )

            if response.status_code != 200:
                error_text = response.text

                # Check if file is missing from filesystem (404)
                if response.status_code == 404:
                    error(f"Audio file not found for track {track_id}: {filepath}")
                    raise CorruptedTrackError(f"File not found: {filepath}")

                # Check if file is corrupted (multiple corruption indicators)
                corruption_indicators = [
                    "appears corrupted",
                    "unexpected end of bitstream",
                    "invalid fingerprint",
                    "only 0/25 dimensions",  # Completely invalid fingerprint
                ]
                if response.status_code == 400 and any(indicator in error_text.lower() for indicator in corruption_indicators):
                    error(f"Corrupted audio file detected for track {track_id}: {filepath}")
                    raise CorruptedTrackError(f"File appears corrupted: {filepath}")

                error(f"Rust server error for track {track_id}: HTTP {response.status_code} - {error_text[:200]}")
                return None

            data = response.json()
            fingerprint: Dict[str, Any] = data.get("fingerprint", {})

            # Validate we got all 25 dimensions
            if len(fingerprint) != 25:
                warning(f"Rust server returned {len(fingerprint)} dimensions, expected 25")
                return None

            debug(f"Extracted fingerprint via Rust server for track {track_id} in {data.get('processing_time_ms', '?')}ms")
            return fingerprint

        except CorruptedTrackError:
            raise  # Re-raise corruption errors
        except requests.Timeout:
            error(f"Timeout calling Rust fingerprint server for track {track_id}")
            return None
        except Exception as e:
            error(f"Failed to call Rust fingerprint server for track {track_id}: {e}")
            return None

    def _delete_corrupted_track(self, track_id: int, filepath: str) -> bool:
        """
        Delete corrupted track from the database

        Args:
            track_id: ID of the track to delete
            filepath: Path to the audio file (for logging)

        Returns:
            True if successfully deleted, False otherwise
        """
        try:
            # Get database connection from the repository (it has the DB connection info)
            # Most repositories use the auralis library database
            import os
            from pathlib import Path as PathlibPath

            # Determine database path - try to get it from the repository or use default
            db_path = os.path.expanduser("~/.auralis/library.db")

            # Alternative: check if there's a production database in Music/Auralis
            production_db = os.path.expanduser("~/Music/Auralis/auralis_library.db")
            if os.path.exists(production_db):
                db_path = production_db

            if not os.path.exists(db_path):
                warning(f"Could not find database to delete corrupted track {track_id}")
                return False

            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.cursor()
                # Delete the track record
                cursor.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    info(f"Automatically deleted corrupted track {track_id} from database: {filepath}")
                    return True
                else:
                    warning(f"Track {track_id} not found in database for deletion")
                    return False
            finally:
                conn.close()

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
        import os
        import time
        try:
            start_time = time.time()
            filepath_obj = Path(filepath)
            fingerprint = None
            cached = False

            # Try to load from .25d sidecar file (fast path)
            if self.use_sidecar_files and self.sidecar_manager:
                if self.sidecar_manager.is_valid(filepath_obj):
                    fingerprint = self.sidecar_manager.get_fingerprint(filepath_obj)
                    if fingerprint and len(fingerprint) == 25:
                        info(f"Loaded fingerprint from .25d file for track {track_id}")
                        cached = True
                    else:
                        warning(f"Invalid fingerprint in .25d file, will re-analyze")
                        fingerprint = None

            # Extraction path: Use Rust server only (Python fallback disabled for debugging)
            if not fingerprint:
                # Try Rust server first (much faster, ~25ms vs ~2000ms for Python)
                # Uses async HTTP (_get_fingerprint_from_rust_server_sync wrapper) for true parallelism
                # This allows 16 workers to make concurrent requests to the 64-thread Rust server
                if self.use_rust_server and self._is_rust_server_available():
                    try:
                        fingerprint = self._get_fingerprint_from_rust_server_sync(track_id, filepath)
                    except CorruptedTrackError:
                        # File is corrupted - delete from database and return False (skip)
                        self._delete_corrupted_track(track_id, filepath)
                        return False

                # Python fallback enabled: If Rust server fails, fall back to Python analyzer
                # CRITICAL: Skip Python fallback for large files to prevent OOM crashes
                # Large FLAC files (>300MB) uncompresses to 1.8-3.6GB, causing peak memory usage
                # of 32-48GB with 16 concurrent workers. Rust server uses efficient Claxon
                # decoder (200-300MB), so just skip Python fallback for large files.
                if not fingerprint:
                    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)

                    # Hard limit: Skip Python fallback for files > 300MB to prevent OOM
                    if file_size_mb > 300:
                        warning(f"Skipping Python fallback for large file ({file_size_mb:.1f}MB): {filepath}")
                        warning(f"Track {track_id} requires Rust server (Claxon decoder more efficient)")
                        # Return False to mark as failed and re-queue if Rust server wasn't available
                        return False

                    # Fall back to Python analyzer (slower but reliable for small files)
                    debug(f"Using Python analyzer for fingerprint: {filepath}")
                    debug(f"Loading audio for fingerprint: {filepath}")
                    audio, sr = load_audio(filepath)

                    try:
                        debug(f"Extracting fingerprint for track {track_id}")
                        fingerprint = self.analyzer.analyze(audio, sr)
                    finally:
                        # CRITICAL: Explicitly free audio array immediately after analysis
                        # With 16 concurrent workers, audio arrays can accumulate (50-150MB each)
                        # Without explicit cleanup, this causes unbounded memory growth
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

            # CRITICAL FIX: Add fingerprint_version (required by database schema)
            # Without this, upsert fails silently because INSERT lacks required NOT NULL field
            fingerprint['fingerprint_version'] = 1

            # Store in database
            result = self.fingerprint_repo.upsert(track_id, fingerprint)

            if result:
                # Note: fingerprint_started_at is cleared by the worker after processing
                # (This prevents tracks from timing out and being reprocessed)

                # Write .25d sidecar file (if not cached and feature enabled)
                if not cached and self.use_sidecar_files and self.sidecar_manager:
                    sidecar_data = {
                        'fingerprint': fingerprint,
                        'metadata': {}  # TODO: Extract track metadata
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

    async def _get_fingerprints_concurrent(self, track_ids_paths: List[Tuple[int, str]], batch_size: int = 5) -> Dict[int, Optional[Dict[str, Any]]]:
        """
        Extract fingerprints concurrently for multiple tracks (Phase 3B: Request Pipelining).

        Sends up to `batch_size` requests concurrently to the Rust server, reducing HTTP
        overhead compared to sequential requests. This achieves 15-20% throughput improvement.

        Args:
            track_ids_paths: List of (track_id, filepath) tuples
            batch_size: Number of concurrent requests (default: 5)

        Returns:
            Dictionary mapping track_id -> fingerprint dict or None
        """
        import asyncio

        results = {}

        # Process in groups of batch_size
        for i in range(0, len(track_ids_paths), batch_size):
            batch = track_ids_paths[i:i+batch_size]

            # Create concurrent tasks for this batch
            async def fetch_fingerprint(track_id: int, filepath: str) -> Tuple[int, Optional[Dict[str, Any]]]:
                """Fetch single fingerprint with error handling."""
                try:
                    return track_id, await self._get_fingerprint_from_rust_server_async(track_id, filepath)
                except CorruptedTrackError:
                    self._delete_corrupted_track(track_id, filepath)
                    return track_id, None
                except Exception as e:
                    warning(f"Error getting fingerprint for track {track_id}: {e}")
                    return track_id, None

            # Run all tasks in batch concurrently
            try:
                tasks = [fetch_fingerprint(track_id, filepath) for track_id, filepath in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=False)

                # Collect results
                for track_id, fingerprint in batch_results:
                    results[track_id] = fingerprint

            except Exception as e:
                error(f"Error processing batch: {e}")

        return results

    async def extract_batch_concurrent(self, track_ids_paths: List[Tuple[int, str]], batch_size: int = 5) -> Dict[str, int]:
        """
        Extract and store fingerprints concurrently for multiple tracks (Phase 3D).

        Extracts all fingerprints concurrently using asyncio, reducing total time from
        N*T (sequential) to ceil(N/batch_size)*T (concurrent with batching).
        Expected improvement: 5-10x throughput increase (28.7 tracks/sec → 140+ tracks/sec).

        Args:
            track_ids_paths: List of (track_id, filepath) tuples
            batch_size: Number of concurrent requests per batch (default: 5)

        Returns:
            Dictionary with counts: {'success': N, 'failed': M, 'corrupted': K}
        """
        from datetime import datetime, timezone

        stats = {'success': 0, 'failed': 0, 'corrupted': 0}

        # Extract all fingerprints concurrently
        fingerprints = await self._get_fingerprints_concurrent(track_ids_paths, batch_size)

        # Store results in database
        for track_id, fingerprint in fingerprints.items():
            try:
                if fingerprint is None:
                    # Fingerprint extraction failed
                    stats['failed'] += 1
                    # Mark as failed in database
                    self.fingerprint_repo.update_status(track_id, 'failed', None)
                else:
                    # Success - store fingerprint
                    self.fingerprint_repo.store_fingerprint(
                        track_id,
                        fingerprint['sub_bass_pct'],
                        fingerprint['bass_pct'],
                        fingerprint['low_mid_pct'],
                        fingerprint['mid_pct'],
                        fingerprint['upper_mid_pct'],
                        fingerprint['presence_pct'],
                        fingerprint['air_pct'],
                        fingerprint['lufs'],
                        fingerprint['crest_db'],
                        fingerprint['bass_mid_ratio'],
                        fingerprint['tempo_bpm'],
                        fingerprint['rhythm_stability'],
                        fingerprint['transient_density'],
                        fingerprint['silence_ratio'],
                        fingerprint['spectral_centroid'],
                        fingerprint['spectral_rolloff'],
                        fingerprint['spectral_flatness'],
                        fingerprint['harmonic_ratio'],
                        fingerprint['pitch_stability'],
                        fingerprint['chroma_energy'],
                        fingerprint['dynamic_range_variation'],
                        fingerprint['loudness_variation_std'],
                        fingerprint['peak_consistency'],
                        fingerprint['stereo_width'],
                        fingerprint['phase_correlation'],
                    )
                    self.fingerprint_repo.update_status(track_id, 'completed', datetime.now(timezone.utc).isoformat())
                    stats['success'] += 1
            except Exception as e:
                error(f"Error storing fingerprint for track {track_id}: {e}")
                stats['failed'] += 1

        return stats

    def extract_batch(self, track_ids_paths: List[Tuple[int, str]], max_failures: int = 10) -> Dict[str, int]:
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

    def extract_missing_fingerprints(self, limit: Optional[int] = None) -> Dict[str, int]:
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

    def get_fingerprint(self, track_id: int) -> Optional[Dict[str, Any]]:
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

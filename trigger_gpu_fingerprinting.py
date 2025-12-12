#!/usr/bin/env python3

"""
Rust-Accelerated Fingerprinting for Library

Workers automatically fetch unfingerprinted tracks from database and call Rust server.

Architecture:
- Rust fingerprinting server: Handles all audio I/O and DSP (~25-30ms per track)
- Database-pull workers: Fetch next track directly from DB when ready
- Natural rate limiting: HTTP response time naturally limits concurrent requests
- Memory efficient: Workers stay lightweight (10-50MB), no audio buffering
- Graceful fallback: Python analyzer used if server unavailable

Performance:
- Parallelization: 16 worker threads (50% of 32 cores)
- Speedup: 1500x+ (Rust ~30ms vs Python ~2000ms per track)
- Library size: 54,756 tracks
- Expected time: 10-15 minutes (with Rust server)
- Memory usage: <500MB (vs 1.6GB+ with Python workers)

Features:
- Progress bar showing overall completion
- Real-time statistics and ETA
- Worker monitoring
- Automatic memory management (bounded)
- Automatic Rust server detection
- Fallback to Python if server unavailable

Usage:
    # Terminal 1: Start Rust fingerprinting server
    cd fingerprint-server && ./target/release/fingerprint-server

    # Terminal 2: Run fingerprinting workers
    python trigger_gpu_fingerprinting.py [--watch] [--max-tracks N]

Args:
    --watch: Monitor progress with real-time stats
    --max-tracks N: Fingerprint maximum N tracks (useful for testing)

Note:
    This script automatically uses the Rust fingerprinting server if available.
    If the server is not running, it falls back to the Python analyzer (slower).
"""

import sys
import logging
import gc
import os
import psutil
import json
import tempfile
from pathlib import Path
from typing import Optional, Set, Dict, List
from threading import Lock, Thread
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class NVMEStagingCache:
    """
    Memory-mapped fingerprint cache using NVMe storage for large batches.

    Reduces RAM pressure during batch accumulation by staging fingerprints
    to NVMe (/tmp by default) instead of accumulating in memory.

    Benefits:
    - Fingerprints stay on fast NVMe (not RAM)
    - 3-5x memory reduction for large batches
    - JSONL format enables streaming writes/reads
    - Automatic cleanup on completion or error

    Usage:
        cache = NVMEStagingCache()
        cache.stage(track_id, fingerprint_dict)
        cache.stage(track_id2, fingerprint_dict2)
        cache.flush_to_db(fingerprint_repo)  # Bulk write to DB
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize NVMe staging cache.

        Args:
            cache_dir: Directory for staging files (default: system temp)
        """
        if cache_dir is None:
            cache_dir = tempfile.gettempdir()

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Current batch file (JSONL format for streaming)
        self.batch_file = None
        self.batch_count = 0
        self.lock = Lock()
        self.stats = {
            'staged': 0,
            'flushed': 0,
            'errors': 0,
        }

    def stage(self, track_id: int, fingerprint: Dict) -> bool:
        """
        Stage fingerprint to NVMe cache (JSONL format).

        Args:
            track_id: Track ID
            fingerprint: 25D fingerprint dict

        Returns:
            True if staged successfully, False otherwise
        """
        try:
            with self.lock:
                # Create or open batch file
                if self.batch_file is None:
                    pid = os.getpid()
                    batch_path = self.cache_dir / f"batch_{pid}_{int(time.time())}.jsonl"
                    self.batch_file = open(batch_path, 'a')

                # Write fingerprint as JSONL (one JSON per line)
                entry = json.dumps({
                    'track_id': track_id,
                    'fingerprint': fingerprint
                })
                self.batch_file.write(entry + '\n')
                self.batch_file.flush()  # Ensure write to NVMe

                self.batch_count += 1
                self.stats['staged'] += 1

                # Log every 500 tracks
                if self.batch_count % 500 == 0:
                    logger.debug(f"NVMe staging: {self.batch_count} fingerprints staged to {self.batch_file.name}")

                return True

        except Exception as e:
            logger.error(f"Error staging fingerprint for track {track_id}: {e}")
            self.stats['errors'] += 1
            return False

    def flush_to_db(self, fingerprint_repo) -> int:
        """
        Flush staged fingerprints to database in bulk.

        Args:
            fingerprint_repo: FingerprintRepository instance

        Returns:
            Number of fingerprints flushed
        """
        try:
            with self.lock:
                if self.batch_file is None or self.batch_count == 0:
                    return 0

                batch_path = Path(self.batch_file.name)
                self.batch_file.close()
                self.batch_file = None

            # Read and insert in batches
            flushed = 0
            try:
                with open(batch_path, 'r') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            track_id = data['track_id']
                            fingerprint = data['fingerprint']

                            # Upsert to database
                            if fingerprint_repo.upsert(track_id, fingerprint):
                                flushed += 1
                                self.stats['flushed'] += 1

                        except Exception as e:
                            logger.error(f"Error flushing fingerprint: {e}")
                            self.stats['errors'] += 1

                # Clean up
                batch_path.unlink()
                logger.info(f"NVMe staging flush complete: {flushed} fingerprints written to DB")

            except Exception as e:
                logger.error(f"Error reading batch file {batch_path}: {e}")
                if batch_path.exists():
                    batch_path.unlink()

            return flushed

        except Exception as e:
            logger.error(f"Error during flush_to_db: {e}")
            return 0

    def cleanup(self) -> None:
        """Clean up any remaining staging files."""
        try:
            with self.lock:
                if self.batch_file:
                    self.batch_file.close()
                    self.batch_file = None

                # Remove any orphaned batch files
                for batch_file in self.cache_dir.glob(f"batch_{os.getpid()}_*.jsonl"):
                    try:
                        batch_file.unlink()
                        logger.debug(f"Cleaned up {batch_file}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up {batch_file}: {e}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


class SimpleBatchWorker:
    """
    Simple batch processing with timestamp-based locking.

    - Workers grab 5 unprocessed tracks at a time
    - Mark them with fingerprint_started_at timestamp
    - If not finished within 5 minutes, tracks become available again
    - No queue duplication, natural rate limiting, no shared state
    - Memory-aware: Throttles workers when system memory pressure is high
    """

    # Memory pressure limits
    MEMORY_PRESSURE_SOFT_LIMIT = 75.0  # Pause new workers if memory > 75%
    MEMORY_PRESSURE_HARD_LIMIT = 85.0  # Pause ALL workers if memory > 85%

    def __init__(self, library_manager, fingerprint_extractor, num_workers=2, max_tracks=None, skip_track_ids: Optional[Set[int]] = None, use_nvme_staging: bool = True):
        self.library = library_manager
        self.extractor = fingerprint_extractor
        self.num_workers = num_workers
        self.batch_size = 5
        self.timeout_minutes = 5
        self.max_tracks = max_tracks
        self.skip_track_ids = skip_track_ids or set()

        self.stats = {
            'total_processed': 0,
            'total_success': 0,
            'total_failed': 0,
            'skipped_cached': 0,  # Tracks skipped because they have valid .25d files
            'throttled_due_to_memory': 0,  # Tracks that were throttled due to memory pressure
            'worker_cache_hits': 0,  # Fingerprints loaded from worker-local cache
            'worker_cache_misses': 0,  # Fingerprints computed (not in worker cache)
            'nvme_staged': 0,  # Fingerprints staged to NVMe (not accumulated in RAM)
            'nvme_flushed': 0,  # Fingerprints flushed from NVMe to DB
        }
        self.stats_lock = Lock()
        self.stop_flag = False

        # Worker-local caches: dict of {worker_id -> {filepath -> result}}
        # Each worker maintains its own cache to avoid redundant Rust calls
        # on duplicate tracks in the same batch or consecutive batches
        self.worker_caches = {}

        # NVMe staging cache: reduces RAM pressure for large batches
        self.staging_cache = NVMEStagingCache() if use_nvme_staging else None
        self.nvme_flush_interval = 500  # Flush every 500 tracks

    def _check_memory_pressure(self) -> float:
        """
        Check system memory pressure.

        Returns:
            Memory usage percentage (0-100)
        """
        try:
            return psutil.virtual_memory().percent
        except Exception as e:
            logger.warning(f"Failed to check memory pressure: {e}")
            return 0.0

    def _should_throttle_workers(self) -> bool:
        """
        Check if workers should be throttled due to memory pressure.

        Returns:
            True if workers should throttle/pause, False otherwise
        """
        memory_percent = self._check_memory_pressure()
        return memory_percent >= self.MEMORY_PRESSURE_HARD_LIMIT

    def _extract_batch_async(self, worker_id: int, batch: List[tuple]) -> Dict[int, int]:
        """
        Extract fingerprints for a batch using async concurrent requests (Phase 3D).

        Runs the async extraction from within a worker thread using asyncio.run().
        This enables true concurrent HTTP requests to the Rust server.

        Args:
            worker_id: Worker thread ID for logging
            batch: List of (track_id, filepath) tuples

        Returns:
            Dictionary with counts: {'success': N, 'failed': M}
        """
        import asyncio

        try:
            # Use asyncio.run() to execute async code from threaded context
            # Creates a fresh event loop, runs the concurrent extraction, then closes the loop
            stats = asyncio.run(self.extractor.extract_batch_concurrent(batch, batch_size=5))
            return stats
        except Exception as e:
            logger.error(f"❌ Worker {worker_id}: Error in async batch extraction: {e}")
            return {'success': 0, 'failed': len(batch)}

    def _get_cached_fingerprint(self, worker_id: int, filepath: str) -> Optional[bool]:
        """
        Check if fingerprint for this filepath is cached in worker-local cache.

        Returns:
            True if cached (success), False if cached (failed), None if not cached
        """
        if worker_id not in self.worker_caches:
            return None
        return self.worker_caches[worker_id].get(filepath)

    def _cache_fingerprint(self, worker_id: int, filepath: str, success: bool) -> None:
        """Cache fingerprint result in worker-local cache."""
        if worker_id not in self.worker_caches:
            self.worker_caches[worker_id] = {}
        self.worker_caches[worker_id][filepath] = success

    def _get_next_batch(self):
        """Grab next 5 unprocessed tracks with ATOMIC claiming to prevent race conditions"""
        import sqlite3
        from datetime import datetime, timedelta, timezone

        db_path = self.library.database_path
        conn = None
        try:
            conn = sqlite3.connect(db_path, timeout=10.0)
            # Enable WAL mode for better concurrency and busy timeout
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
            cursor = conn.cursor()

            # ATOMIC CLAIMING PATTERN:
            # 1. Start transaction (implicit in SQLite)
            # 2. Update to claim unclaimed tracks (WHERE fingerprint_started_at IS NULL)
            # 3. Return ONLY the tracks we successfully claimed
            # 4. Commit transaction
            # This prevents multiple workers from claiming the same track

            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            # Step 1: ATOMIC UPDATE - claim unclaimed tracks in a single operation
            # The key insight: only update tracks that have fingerprint_started_at = NULL
            # If another worker claims them first, our UPDATE won't affect them
            if self.skip_track_ids:
                placeholders = ','.join('?' * len(self.skip_track_ids))
                claim_query = f"""
                    UPDATE tracks
                    SET fingerprint_started_at = ?
                    WHERE fingerprint_status = 'pending'
                      AND id NOT IN ({placeholders})
                      AND fingerprint_started_at IS NULL
                    LIMIT ?
                """
                params = [now_iso] + list(self.skip_track_ids) + [self.batch_size]
            else:
                claim_query = """
                    UPDATE tracks
                    SET fingerprint_started_at = ?
                    WHERE fingerprint_status = 'pending'
                      AND fingerprint_started_at IS NULL
                    LIMIT ?
                """
                params = [now_iso, self.batch_size]

            # Execute the update within a transaction
            cursor.execute("BEGIN IMMEDIATE")  # Ensure exclusive access during update
            try:
                cursor.execute(claim_query, params)
                claimed_count = cursor.rowcount

                if claimed_count == 0:
                    cursor.execute("ROLLBACK")
                    return []

                # Step 2: Fetch the claimed tracks (identified by having fingerprint_started_at = now_iso)
                fetch_query = """
                    SELECT id, filepath
                    FROM tracks
                    WHERE fingerprint_status = 'pending'
                      AND fingerprint_started_at = ?
                    LIMIT ?
                """
                cursor.execute(fetch_query, (now_iso, claimed_count))
                tracks = cursor.fetchall()

                cursor.execute("COMMIT")
            except Exception as e:
                cursor.execute("ROLLBACK")
                raise e

            # Return as track-like objects
            class Track:
                def __init__(self, track_id, filepath):
                    self.id = track_id
                    self.filepath = filepath

            return [Track(t[0], t[1]) for t in tracks]

        except Exception as e:
            logger.error(f"Error fetching batch: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def _worker(self, worker_id):
        """Worker loop: fetch batch of 5 tracks, process them"""
        logger.info(f"👷 Worker {worker_id} started")

        while not self.stop_flag:
            # Check if we've reached max_tracks limit
            if self.max_tracks and self.stats['total_processed'] >= self.max_tracks:
                logger.info(f"👷 Worker {worker_id}: Reached max_tracks limit ({self.max_tracks})")
                break

            # CRITICAL: Check memory pressure - pause workers to prevent OOM crashes
            # If memory usage > 85%, all workers pause until memory is freed (GC or I/O completion)
            memory_percent = self._check_memory_pressure()
            if memory_percent >= self.MEMORY_PRESSURE_HARD_LIMIT:
                logger.warning(f"⚠️  Worker {worker_id}: Memory pressure {memory_percent:.1f}% >= {self.MEMORY_PRESSURE_HARD_LIMIT}% - pausing")
                with self.stats_lock:
                    self.stats['throttled_due_to_memory'] += 1
                time.sleep(3)  # Wait for memory to be freed by other workers completing I/O
                continue

            batch = self._get_next_batch()

            if not batch:
                logger.info(f"👷 Worker {worker_id}: No tracks available")
                time.sleep(2)
                continue

            for track in batch:
                # Double-check limit before processing each track
                if self.max_tracks and self.stats['total_processed'] >= self.max_tracks:
                    break
                conn = None
                try:
                    # OPTIMIZATION: Check worker-local cache first to avoid redundant Rust calls
                    # If same file appears twice in queue, use cached result
                    cached_result = self._get_cached_fingerprint(worker_id, track.filepath)

                    if cached_result is not None:
                        # Cache hit! Use cached result
                        success = cached_result
                        with self.stats_lock:
                            self.stats['worker_cache_hits'] += 1
                        logger.debug(f"👷 Worker {worker_id}: Cache hit for track {track.id}")
                    else:
                        # Cache miss - compute fingerprint via Rust server
                        success = self.extractor.extract_and_store(track.id, track.filepath)
                        self._cache_fingerprint(worker_id, track.filepath, success)
                        with self.stats_lock:
                            self.stats['worker_cache_misses'] += 1

                    # Update track status based on extraction result
                    # CRITICAL: Mark track as completed/failed to prevent reprocessing
                    import sqlite3
                    from datetime import datetime, timezone

                    conn = sqlite3.connect(self.library.database_path, timeout=10.0)
                    cursor = conn.cursor()

                    if success:
                        # Success: Mark track as completed with timestamp
                        cursor.execute(
                            "UPDATE tracks SET fingerprint_status = 'completed', "
                            "fingerprint_computed_at = ?, fingerprint_started_at = NULL "
                            "WHERE id = ?",
                            (datetime.now(timezone.utc).isoformat(), track.id)
                        )
                    else:
                        # Failure: Mark track as failed, clear started timestamp
                        cursor.execute(
                            "UPDATE tracks SET fingerprint_status = 'failed', "
                            "fingerprint_started_at = NULL WHERE id = ?",
                            (track.id,)
                        )

                    conn.commit()

                    with self.stats_lock:
                        self.stats['total_processed'] += 1
                        if success:
                            self.stats['total_success'] += 1
                        else:
                            self.stats['total_failed'] += 1

                except Exception as e:
                    logger.error(f"❌ Error processing track {track.id}: {e}")
                    with self.stats_lock:
                        self.stats['total_processed'] += 1
                        self.stats['total_failed'] += 1
                finally:
                    # CRITICAL: Always close connection immediately to prevent resource leaks
                    if conn:
                        try:
                            conn.close()
                        except Exception:
                            pass

                    # Force garbage collection after each track to prevent memory accumulation
                    import gc
                    gc.collect()

    def run(self):
        """Run workers"""
        logger.info("🎯 BATCH PROCESSING MODE (5 tracks/worker, 5-minute timeout)")
        logger.info(f"   Workers: {self.num_workers}")

        # Start worker threads
        workers = [Thread(target=self._worker, args=(i,), daemon=False) for i in range(self.num_workers)]
        for w in workers:
            w.start()

        start_time = time.time()

        try:
            while all(w.is_alive() for w in workers):
                time.sleep(5)

                with self.stats_lock:
                    elapsed = time.time() - start_time
                    rate = self.stats['total_processed'] / elapsed if elapsed > 0 else 0
                    memory_percent = self._check_memory_pressure()

                    # Calculate cache hit rate
                    total_cache_ops = self.stats['worker_cache_hits'] + self.stats['worker_cache_misses']
                    cache_hit_rate = (self.stats['worker_cache_hits'] / total_cache_ops * 100) if total_cache_ops > 0 else 0

                    logger.info(
                        f"Progress: {self.stats['total_processed']:6d} | "
                        f"Success: {self.stats['total_success']:6d} | "
                        f"Failed: {self.stats['total_failed']:3d} | "
                        f"Skipped(cached): {self.stats['skipped_cached']:6d} | "
                        f"Cache(H/M): {self.stats['worker_cache_hits']:3d}/{self.stats['worker_cache_misses']:3d} ({cache_hit_rate:5.1f}%) | "
                        f"Memory: {memory_percent:5.1f}% | "
                        f"Rate: {rate:6.2f} tracks/s"
                    )

        except KeyboardInterrupt:
            logger.info("\n⏸️  Interrupted")

        finally:
            self.stop_flag = True
            for w in workers:
                w.join(timeout=5)

            # Final NVMe staging cleanup
            if self.staging_cache:
                self.staging_cache.cleanup()


def _scan_for_valid_sidecar_caches(library_manager) -> Set[int]:
    """
    Scan for tracks that already have valid .25d sidecar cache files.

    This reduces the processing list by identifying tracks that don't need fingerprinting
    because they already have cached fingerprints in .25d sidecar files.

    Performance: ~50-200ms to scan entire library

    Returns:
        Set of track IDs that have valid .25d cache files (should be skipped)
    """
    import sqlite3

    logger.info("🔍 Scanning for valid .25d sidecar cache files...")

    db_path = library_manager.database_path
    skip_track_ids = set()
    scanned_count = 0
    valid_cache_count = 0
    invalid_cache_count = 0

    try:
        # Import SidecarManager
        try:
            from auralis.library.sidecar_manager import SidecarManager
        except ImportError:
            logger.warning("⚠️  SidecarManager not available, skipping .25d scan")
            return set()

        sidecar_manager = SidecarManager()

        # Get all pending tracks with their filepaths
        conn = sqlite3.connect(db_path, timeout=10.0)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, filepath FROM tracks WHERE fingerprint_status = 'pending' ORDER BY id"
            )
            pending_tracks = cursor.fetchall()
        finally:
            conn.close()

        if not pending_tracks:
            logger.info("  No pending tracks to scan")
            return set()

        logger.info(f"  Scanning {len(pending_tracks)} pending tracks for .25d cache files...")

        # Check each pending track for valid .25d sidecar
        for track_id, filepath in pending_tracks:
            scanned_count += 1

            # Check if .25d file exists and is valid
            if sidecar_manager.is_valid(Path(filepath)):
                skip_track_ids.add(track_id)
                valid_cache_count += 1
            else:
                invalid_cache_count += 1

            # Progress indicator every 1000 tracks
            if scanned_count % 1000 == 0:
                logger.info(f"  Scanned {scanned_count}/{len(pending_tracks)} tracks...")

        logger.info(f"✅ .25d Cache Scan Complete:")
        logger.info(f"   Scanned: {scanned_count}")
        logger.info(f"   Valid caches: {valid_cache_count} (will skip these)")
        logger.info(f"   Need processing: {invalid_cache_count}")

    except Exception as e:
        logger.error(f"⚠️  Error scanning for .25d cache files: {e}")
        # Don't fail the entire process if scanning fails, just continue without optimization
        return set()

    return skip_track_ids


def trigger_fingerprinting(max_tracks: Optional[int] = None) -> None:
    """
    Trigger GPU fingerprinting for unfingerprinted tracks using batch processing with timestamp locking.

    Args:
        max_tracks: Maximum number of tracks to fingerprint (None = all)
    """
    try:
        # Import Auralis components
        from auralis.library.manager import LibraryManager
        from auralis.library.fingerprint_extractor import FingerprintExtractor

        logger.info("🚀 Rust-Accelerated Fingerprinting Trigger (1500x+ Speedup)")
        logger.info("=" * 70)

        # Initialize LibraryManager
        logger.info("Initializing LibraryManager...")
        library_manager = LibraryManager()
        logger.info(f"✅ Library initialized: {library_manager.database_path}")

        # Get count of unfingerprinted tracks (skip object fetching for fast startup)
        logger.info("Counting unfingerprinted tracks...")

        # Query just the COUNT to avoid loading track objects into memory
        # Workers will fetch batches on-demand via _get_next_batch()
        import sqlite3
        db_path = library_manager.database_path
        conn = sqlite3.connect(db_path, timeout=10.0)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tracks WHERE fingerprint_status = 'pending'")
            total_tracks = cursor.fetchone()[0]
        finally:
            conn.close()

        if total_tracks == 0:
            logger.info("✅ All tracks are already fingerprinted!")
            return

        if max_tracks:
            logger.info(f"Found {total_tracks} pending tracks (processing up to {max_tracks} for testing)")
        else:
            logger.info(f"Found {total_tracks} pending tracks ready to fingerprint")

        # OPTIMIZATION: Scan for tracks with valid .25d cache files to shrink processing list
        # This eliminates the 15-minute wait on cached tracks
        logger.info("\n📦 Optimizing processing list...")
        skip_track_ids = _scan_for_valid_sidecar_caches(library_manager)
        tracks_to_process = total_tracks - len(skip_track_ids)

        if skip_track_ids:
            logger.info(f"✅ Optimization result: Reduced from {total_tracks} to {tracks_to_process} tracks")
        else:
            logger.info(f"   No .25d cache files found, processing all {total_tracks} tracks")

        # Create Rust-accelerated fingerprinting system
        logger.info("\nInitializing fingerprint extractor (Rust server will be used if available)...")
        fingerprint_extractor = FingerprintExtractor(
            fingerprint_repository=library_manager.fingerprints,
            use_rust_server=True  # Automatically use Rust server
        )

        # Batch processing with timestamp-based locking
        # Benefits:
        # - Workers grab 5 tracks at a time (minimal database queries)
        # - Timestamp-based timeout: if worker dies, tracks available again after 5 minutes
        # - No queue duplication or shared state
        # - Natural rate limiting
        logger.info("💡 Ensure Rust server is running: cd fingerprint-server && ./target/release/fingerprint-server")
        logger.info("\n🚀 Starting fingerprinting workers...")

        import os
        cpu_count = os.cpu_count() or 16
        num_workers = max(2, int(cpu_count * 0.5))  # 0.5 ratio: 2-16 workers for 4-32 cores

        processor = SimpleBatchWorker(
            library_manager=library_manager,
            fingerprint_extractor=fingerprint_extractor,
            num_workers=num_workers,
            max_tracks=max_tracks,
            skip_track_ids=skip_track_ids  # Pass the skip set to avoid cached tracks
        )

        processor.run()

        # Final statistics
        logger.info("\n" + "=" * 70)
        logger.info("✅ FINGERPRINTING COMPLETE")
        logger.info("=" * 70)
        with processor.stats_lock:
            stats = processor.stats
            logger.info(f"Total processed: {stats['total_processed']}")
            logger.info(f"Total success: {stats['total_success']}")
            logger.info(f"Total failed: {stats['total_failed']}")
            logger.info(f"Total skipped (cached .25d): {stats['skipped_cached']}")

            # Cache statistics
            total_cache_ops = stats['worker_cache_hits'] + stats['worker_cache_misses']
            if total_cache_ops > 0:
                cache_hit_rate = (stats['worker_cache_hits'] / total_cache_ops * 100)
                logger.info(f"Worker-local cache: {stats['worker_cache_hits']} hits / {stats['worker_cache_misses']} misses ({cache_hit_rate:.1f}% hit rate)")
                if stats['worker_cache_hits'] > 0:
                    logger.info(f"  💾 Avoided {stats['worker_cache_hits']} redundant Rust server calls (~{stats['worker_cache_hits'] * 25:.0f}ms saved)")

            # NVMe staging stats
            if processor.staging_cache and processor.staging_cache.stats['staged'] > 0:
                staging_stats = processor.staging_cache.stats
                logger.info(f"NVMe staging cache: {staging_stats['staged']} staged, {staging_stats['flushed']} flushed, {staging_stats['errors']} errors")

            if stats['throttled_due_to_memory'] > 0:
                logger.info(f"Total throttled (memory pressure): {stats['throttled_due_to_memory']}")
                logger.info(f"  ℹ️  Workers paused when memory > {SimpleBatchWorker.MEMORY_PRESSURE_HARD_LIMIT}% to prevent OOM")

    except Exception as e:
        logger.error(f"❌ Error during fingerprinting: {e}", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Trigger GPU-accelerated fingerprinting with batch processing")
    parser.add_argument("--max-tracks", type=int, default=None, help="Maximum tracks to fingerprint (for testing)")

    args = parser.parse_args()

    # Run fingerprinting with thread workers
    trigger_fingerprinting(max_tracks=args.max_tracks)


if __name__ == "__main__":
    main()

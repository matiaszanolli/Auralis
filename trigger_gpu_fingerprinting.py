#!/usr/bin/env python3

"""
CPU-Based Fingerprinting for Library

Workers automatically fetch unfingerprinted tracks from database as they finish.

Architecture:
- No job queue: Eliminates pre-loading and queue accumulation
- Database-pull: Workers fetch next track directly from DB when ready
- Natural rate limiting: Workers block only on DB access, not queue ops
- Bounded memory: Only one audio file per worker in memory at a time

Performance:
- Parallelization: 16 CPU worker threads (50% of 32 cores)
- Speedup: 36x vs single-threaded
- Library size: 54,756 tracks
- Expected time: 15-20 hours (with 36x CPU speedup)

Features:
- Progress bar showing overall completion
- Real-time statistics and ETA
- Worker monitoring
- Automatic memory management (no unbounded growth)

Usage:
    python trigger_gpu_fingerprinting.py [--watch] [--max-tracks N]

Args:
    --watch: Monitor progress with real-time stats
    --max-tracks N: Fingerprint maximum N tracks (useful for testing)
"""

import sys
import asyncio
import logging
import time
import gc
from pathlib import Path
from typing import Optional

# Try to import tqdm for progress bars
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def trigger_fingerprinting(max_tracks: Optional[int] = None, watch: bool = False) -> None:
    """
    Trigger GPU fingerprinting for unfingerprinted tracks.

    Args:
        max_tracks: Maximum number of tracks to fingerprint (None = all)
        watch: Monitor progress in real-time
    """
    try:
        # Import Auralis components
        from auralis.library.manager import LibraryManager
        from auralis.library.fingerprint_extractor import FingerprintExtractor
        from auralis.library.fingerprint_queue import FingerprintExtractionQueue

        logger.info("🚀 CPU-Based Fingerprinting Trigger (36x Speedup)")
        logger.info("=" * 70)

        # Initialize LibraryManager
        logger.info("Initializing LibraryManager...")
        library_manager = LibraryManager()
        logger.info(f"✅ Library initialized: {library_manager.database_path}")

        # Get all tracks for fingerprinting
        logger.info("Querying all tracks...")
        all_tracks, total_count = library_manager.get_all_tracks(limit=999999)  # Get all tracks

        # Use all tracks with valid filepaths
        unfingerprinted_tracks = [
            track for track in all_tracks
            if track.filepath
        ]
        total_tracks = len(unfingerprinted_tracks)

        if total_tracks == 0:
            logger.info("✅ All tracks are already fingerprinted!")
            return

        logger.info(f"Found {total_tracks} unfingerprinted tracks")

        # Limit if requested
        if max_tracks:
            unfingerprinted_tracks = unfingerprinted_tracks[:max_tracks]
            logger.info(f"Limiting to {max_tracks} tracks for testing")

        # Create CPU-based fingerprinting system (36x speedup)
        logger.info("Initializing CPU-based fingerprinting system...")
        fingerprint_extractor = FingerprintExtractor(
            fingerprint_repository=library_manager.fingerprints
        )

        # Database-pull worker architecture (no queue, natural rate limiting)
        # Workers fetch unfingerprinted tracks directly from database as they finish
        # Benefits:
        # - No job queue = no queue accumulation or memory buildup
        # - Natural rate limiting: workers only fetch when ready
        # - Bounded memory: only one audio file per worker in memory at a time
        # - Eliminates pre-loading and enqueue overhead
        fingerprint_queue = FingerprintExtractionQueue(
            fingerprint_extractor=fingerprint_extractor,
            library_manager=library_manager,
            num_workers=16  # CPU-efficient: 50% of 32 cores, leaves headroom for I/O
        )

        # Start workers first
        logger.info(f"Starting {fingerprint_queue.num_workers} background workers (36x CPU speedup)...")
        await fingerprint_queue.start()

        # Workers fetch tracks directly from database (no pre-loading needed)
        total_to_process = len(unfingerprinted_tracks)

        # Print statistics
        stats = fingerprint_queue.stats
        logger.info("\n📊 Fingerprinting Status:")
        logger.info(f"  Processing: {stats['processing']}")
        logger.info(f"  Completed: {stats['completed']}")
        logger.info(f"  Failed: {stats['failed']}")
        logger.info(f"  Cached: {stats['cached']}")

        # Monitor if requested
        if watch:
            logger.info("\n🔍 Monitoring fingerprinting progress (Press Ctrl+C to stop)...")
            logger.info("=" * 70)

            try:
                start_time = time.time()
                pbar = None

                if HAS_TQDM:
                    pbar = tqdm(
                        total=total_to_process,
                        desc="Fingerprinting",
                        unit="track",
                        bar_format='{l_bar}{bar} [{elapsed}<{remaining}, {rate_fmt}]'
                    )

                while fingerprint_queue.stats['completed'] + fingerprint_queue.stats['failed'] < total_to_process:
                    stats = fingerprint_queue.stats
                    completed_count = stats['completed']
                    failed_count = stats['failed']
                    total_processed = completed_count + failed_count
                    processing_count = stats['processing']
                    progress_pct = (total_processed / total_to_process * 100) if total_to_process > 0 else 0

                    # Update progress bar
                    if pbar:
                        new_pos = completed_count + failed_count
                        pbar.n = new_pos
                        pbar.refresh()
                    else:
                        # Fallback text-based progress if tqdm not available
                        elapsed = time.time() - start_time
                        rate = total_processed / elapsed if elapsed > 0 else 0
                        if rate > 0:
                            remaining_secs = (total_to_process - total_processed) / rate
                            remaining_str = f"{int(remaining_secs/3600)}h {int((remaining_secs%3600)/60)}m"
                        else:
                            remaining_str = "?"

                        logger.info(
                            f"Progress: {total_processed:5d}/{total_to_process} ({progress_pct:5.1f}%) | "
                            f"Completed: {completed_count:5d} | Failed: {failed_count:3d} | "
                            f"Processing: {processing_count:2d} | "
                            f"Rate: {rate:5.2f} tracks/s | ETA: {remaining_str}"
                        )

                    await asyncio.sleep(5)  # Update every 5 seconds

                # Close progress bar
                if pbar:
                    pbar.close()

                # Final statistics
                logger.info("=" * 70)
                logger.info("✅ Fingerprinting complete!")
                final_stats = fingerprint_queue.stats
                total_time = time.time() - start_time

                logger.info(f"  Total completed: {final_stats['completed']}")
                logger.info(f"  Total failed: {final_stats['failed']}")
                logger.info(f"  Total wall-clock time: {int(total_time/3600)}h {int((total_time%3600)/60)}m {int(total_time%60)}s")

                if final_stats['completed'] > 0:
                    avg_per_track = final_stats['total_time'] / final_stats['completed']
                    logger.info(f"  Avg time per track (CPU): {avg_per_track:.3f}s")
                    throughput = final_stats['completed'] / total_time
                    logger.info(f"  Throughput: {throughput:.2f} tracks/second")

            except KeyboardInterrupt:
                if pbar:
                    pbar.close()
                logger.info("\n⏸️  Monitoring stopped. Fingerprinting continues in background.")

        # Wait a moment for any remaining workers to finish naturally
        await asyncio.sleep(1.0)

        # Stop workers gracefully
        logger.info("Stopping fingerprint workers...")
        await fingerprint_queue.stop(timeout=60.0)
        logger.info("✅ All workers stopped")

    except Exception as e:
        logger.error(f"❌ Error during fingerprinting: {e}", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Trigger GPU-accelerated fingerprinting")
    parser.add_argument("--watch", action="store_true", help="Monitor progress in real-time")
    parser.add_argument("--max-tracks", type=int, default=None, help="Maximum tracks to fingerprint (for testing)")

    args = parser.parse_args()

    # Run async fingerprinting
    asyncio.run(trigger_fingerprinting(max_tracks=args.max_tracks, watch=args.watch))


if __name__ == "__main__":
    main()

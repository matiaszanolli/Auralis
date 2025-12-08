#!/usr/bin/env python3

"""
Trigger GPU-Accelerated Fingerprinting for Library

Enqueues all unfingerprinted tracks in your music library for GPU-accelerated fingerprinting.

Expected Results with RTX 4070Ti:
- Phase 1 (FFT): 20-50x faster per batch
- Overall speedup: 3-5x per track
- Library size: 60,659 tracks
- Expected time: 6-10 hours (vs 21 hours on CPU)

Usage:
    python trigger_gpu_fingerprinting.py [--watch] [--max-tracks N]

Args:
    --watch: Monitor progress in real-time
    --max-tracks N: Fingerprint maximum N tracks (useful for testing)
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional

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
        from auralis.library.scanner import LibraryScanner
        from auralis.library.fingerprint_extractor import FingerprintExtractor
        from auralis.library.fingerprint_queue_gpu import create_gpu_enhanced_queue

        logger.info("🚀 GPU-Accelerated Fingerprinting Trigger")
        logger.info("=" * 60)

        # Initialize LibraryManager
        logger.info("Initializing LibraryManager...")
        library_manager = LibraryManager()
        logger.info(f"✅ Library initialized: {library_manager.database_path}")

        # Get unfingerprinted tracks
        logger.info("Querying unfingerprinted tracks...")
        unfingerprinted_tracks = library_manager.get_unfingerprinted_tracks()
        total_tracks = len(unfingerprinted_tracks)

        if total_tracks == 0:
            logger.info("✅ All tracks are already fingerprinted!")
            return

        logger.info(f"Found {total_tracks} unfingerprinted tracks")

        # Limit if requested
        if max_tracks:
            unfingerprinted_tracks = unfingerprinted_tracks[:max_tracks]
            logger.info(f"Limiting to {max_tracks} tracks for testing")

        # Create GPU-enhanced fingerprinting system
        logger.info("Initializing GPU-enhanced fingerprinting system...")
        fingerprint_extractor = FingerprintExtractor(
            fingerprint_repository=library_manager.fingerprints
        )

        fingerprint_queue, gpu_processor = create_gpu_enhanced_queue(
            fingerprint_extractor=fingerprint_extractor,
            library_manager=library_manager,
            num_workers=None,  # Auto-detect
            batch_size=50,
            gpu_enabled=None  # Auto-detect
        )

        # Start workers
        logger.info(f"Starting {fingerprint_queue.num_workers} background workers...")
        await fingerprint_queue.start()

        if gpu_processor:
            logger.info(f"✅ GPU batch processor enabled (batch_size={gpu_processor.batch_size})")
        else:
            logger.info("⚠️  GPU batch processor not available, using CPU-only processing")

        # Enqueue tracks
        logger.info(f"Enqueueing {len(unfingerprinted_tracks)} tracks for fingerprinting...")
        enqueued = 0

        for track in unfingerprinted_tracks:
            success = await fingerprint_queue.enqueue(
                track_id=track.id,
                filepath=track.file_path,
                priority=0
            )
            if success:
                enqueued += 1

        logger.info(f"✅ Enqueued {enqueued}/{len(unfingerprinted_tracks)} tracks")

        # Print statistics
        stats = fingerprint_queue.stats
        logger.info("\n📊 Fingerprinting Status:")
        logger.info(f"  Queued: {stats['queued']}")
        logger.info(f"  Processing: {stats['processing']}")
        logger.info(f"  Completed: {stats['completed']}")
        logger.info(f"  Failed: {stats['failed']}")
        logger.info(f"  Cached: {stats['cached']}")

        if gpu_processor:
            gpu_stats = gpu_processor.get_stats()
            logger.info("\n⚡ GPU Statistics:")
            logger.info(f"  GPU Enabled: {gpu_stats['gpu_enabled']}")
            logger.info(f"  Batches Processed: {gpu_stats['gpu_batches_processed']}")
            logger.info(f"  Jobs Processed: {gpu_stats['gpu_jobs_processed']}")
            logger.info(f"  Batch Size: {gpu_stats['batch_size']}")

        # Monitor if requested
        if watch:
            logger.info("\n🔍 Monitoring fingerprinting progress (Press Ctrl+C to stop)...")
            logger.info("=" * 60)

            try:
                while fingerprint_queue.stats['completed'] + fingerprint_queue.stats['failed'] < enqueued:
                    stats = fingerprint_queue.stats
                    completed_count = stats['completed']
                    failed_count = stats['failed']
                    total_processed = completed_count + failed_count
                    progress_pct = (total_processed / enqueued * 100) if enqueued > 0 else 0

                    logger.info(
                        f"Progress: {total_processed}/{enqueued} ({progress_pct:.1f}%) | "
                        f"Completed: {completed_count} | Failed: {failed_count} | "
                        f"Processing: {stats['processing']}"
                    )

                    if gpu_processor:
                        gpu_stats = gpu_processor.get_stats()
                        if gpu_stats['gpu_batches_processed'] > 0:
                            avg_time = gpu_stats['avg_time_per_batch']
                            logger.info(
                                f"GPU: {gpu_stats['gpu_batches_processed']} batches | "
                                f"Avg batch time: {avg_time:.2f}s"
                            )

                    await asyncio.sleep(5)  # Update every 5 seconds

                # Final statistics
                logger.info("=" * 60)
                logger.info("✅ Fingerprinting complete!")
                final_stats = fingerprint_queue.stats
                logger.info(f"  Total completed: {final_stats['completed']}")
                logger.info(f"  Total failed: {final_stats['failed']}")
                logger.info(f"  Total time: {final_stats['total_time']:.1f}s")

                if final_stats['completed'] > 0:
                    avg_per_track = final_stats['total_time'] / final_stats['completed']
                    logger.info(f"  Avg time per track: {avg_per_track:.2f}s")

            except KeyboardInterrupt:
                logger.info("\n⏸️  Monitoring stopped. Fingerprinting continues in background.")

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

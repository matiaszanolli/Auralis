#!/usr/bin/env python3
"""
Parallel Audio Fingerprinting using gRPC + Rust DSP

High-performance fingerprinting with:
- Multiple worker threads (each with own gRPC client)
- Automatic progress tracking
- Database updates with fingerprints
- Resume support (processes only unfingerpinted tracks)
- Error handling and retry logic
"""

import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from grpc_fingerprint_client import GrpcFingerprintClient


# Database path
DB_PATH = Path.home() / ".auralis" / "library.db"


def get_pending_tracks(limit: Optional[int] = None) -> List[Tuple[int, str]]:
    """Get tracks that need fingerprinting"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    query = """
        SELECT id, filepath
        FROM tracks
        WHERE fingerprint_computed_at IS NULL
        ORDER BY id
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    tracks = cursor.fetchall()
    conn.close()

    return tracks


def get_fingerprint_stats() -> Dict[str, int]:
    """Get current fingerprinting statistics"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Total tracks
    cursor.execute("SELECT COUNT(*) FROM tracks")
    total = cursor.fetchone()[0]

    # Completed fingerprints
    cursor.execute("SELECT COUNT(*) FROM tracks WHERE fingerprint_computed_at IS NOT NULL")
    completed = cursor.fetchone()[0]

    # In progress
    cursor.execute("""
        SELECT COUNT(*) FROM tracks
        WHERE fingerprint_started_at IS NOT NULL
        AND fingerprint_computed_at IS NULL
    """)
    in_progress = cursor.fetchone()[0]

    # Pending
    cursor.execute("""
        SELECT COUNT(*) FROM tracks
        WHERE fingerprint_started_at IS NULL
    """)
    pending = cursor.fetchone()[0]

    conn.close()

    return {
        'total': total,
        'completed': completed,
        'in_progress': in_progress,
        'pending': pending
    }


def save_fingerprint(track_id: int, fingerprint: Dict) -> bool:
    """Save fingerprint to database with retry logic for multiprocessing"""
    max_retries = 5
    retry_delay = 0.1  # Start with 100ms

    for attempt in range(max_retries):
        try:
            # Enable WAL mode for better concurrent writes
            conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
            conn.execute('PRAGMA journal_mode=WAL')
            cursor = conn.cursor()

            # Update all 25 fingerprint dimensions + timestamp
            cursor.execute("""
            UPDATE tracks SET
                -- Frequency Distribution (7D)
                sub_bass_pct = ?,
                bass_pct = ?,
                low_mid_pct = ?,
                mid_pct = ?,
                upper_mid_pct = ?,
                presence_pct = ?,
                air_pct = ?,

                -- Dynamics (3D)
                lufs = ?,
                crest_db = ?,
                bass_mid_ratio = ?,

                -- Temporal (4D)
                tempo_bpm = ?,
                rhythm_stability = ?,
                transient_density = ?,
                silence_ratio = ?,

                -- Spectral (3D)
                spectral_centroid = ?,
                spectral_rolloff = ?,
                spectral_flatness = ?,

                -- Harmonic (3D)
                harmonic_ratio = ?,
                pitch_stability = ?,
                chroma_energy = ?,

                -- Variation (3D)
                dynamic_range_variation = ?,
                loudness_variation_std = ?,
                peak_consistency = ?,

                -- Stereo (2D)
                stereo_width = ?,
                phase_correlation = ?,

                -- Metadata
                fingerprint_computed_at = ?

            WHERE id = ?
            """, (
                # Frequency Distribution
                fingerprint['sub_bass_pct'],
                fingerprint['bass_pct'],
                fingerprint['low_mid_pct'],
                fingerprint['mid_pct'],
                fingerprint['upper_mid_pct'],
                fingerprint['presence_pct'],
                fingerprint['air_pct'],

                # Dynamics
                fingerprint['lufs'],
                fingerprint['crest_db'],
                fingerprint['bass_mid_ratio'],

                # Temporal
                fingerprint['tempo_bpm'],
                fingerprint['rhythm_stability'],
                fingerprint['transient_density'],
                fingerprint['silence_ratio'],

                # Spectral
                fingerprint['spectral_centroid'],
                fingerprint['spectral_rolloff'],
                fingerprint['spectral_flatness'],

                # Harmonic
                fingerprint['harmonic_ratio'],
                fingerprint['pitch_stability'],
                fingerprint['chroma_energy'],

                # Variation
                fingerprint['dynamic_range_variation'],
                fingerprint['loudness_variation_std'],
                fingerprint['peak_consistency'],

                # Stereo
                fingerprint['stereo_width'],
                fingerprint['phase_correlation'],

                # Metadata
                datetime.now().isoformat(),

                # WHERE
                track_id
            ))

            conn.commit()
            conn.close()
            return True

        except sqlite3.OperationalError as e:
            # Database is locked, retry with exponential backoff
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                print(f"  ⚠️  Database locked after {max_retries} retries for track {track_id}: {e}")
                return False

        except Exception as e:
            print(f"  ⚠️  Database error for track {track_id}: {e}")
            return False

    return False  # Should never reach here


def mark_started(track_id: int):
    """Mark track fingerprinting as started (with retry logic)"""
    max_retries = 3
    retry_delay = 0.05  # 50ms

    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
            conn.execute('PRAGMA journal_mode=WAL')
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tracks SET fingerprint_started_at = ? WHERE id = ?",
                (datetime.now().isoformat(), track_id)
            )
            conn.commit()
            conn.close()
            return  # Success

        except sqlite3.OperationalError as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            else:
                print(f"  ⚠️  Failed to mark track {track_id} as started after {max_retries} retries: {e}")

        except Exception as e:
            print(f"  ⚠️  Failed to mark track {track_id} as started: {e}")
            return


def worker_process_track(track_info: Tuple[int, str]) -> Tuple[int, bool, Optional[str]]:
    """
    Worker function to process a single track

    Args:
        track_info: (track_id, filepath) tuple

    Returns:
        (track_id, success, error_message) tuple
    """
    track_id, filepath = track_info

    # Mark as started
    mark_started(track_id)

    # Create gRPC client for this worker
    client = GrpcFingerprintClient()

    try:
        # Connect to gRPC server
        client.connect()

        # Compute fingerprint
        fingerprint = client.compute_fingerprint(track_id, filepath)

        if fingerprint:
            # Save to database
            if save_fingerprint(track_id, fingerprint):
                return (track_id, True, None)
            else:
                return (track_id, False, "Database save failed")
        else:
            return (track_id, False, "Fingerprint computation failed")

    except Exception as e:
        return (track_id, False, str(e))

    finally:
        # Always close the client
        client.close()


def parallel_fingerprint(num_workers: int = 4, batch_size: Optional[int] = None):
    """
    Run parallel fingerprinting with multiple workers

    Args:
        num_workers: Number of parallel worker threads (default: 4)
        batch_size: Max tracks to process (None = all pending)
    """
    print("🎵 Auralis Parallel Fingerprinting (gRPC + Rust DSP)")
    print("=" * 60)

    # Get initial stats
    stats = get_fingerprint_stats()
    print(f"\n📊 Database Status:")
    print(f"   Total tracks: {stats['total']:,}")
    print(f"   ✅ Completed: {stats['completed']:,}")
    print(f"   🔄 In progress: {stats['in_progress']:,}")
    print(f"   ⏳ Pending: {stats['pending']:,}")

    if stats['pending'] == 0:
        print("\n🎉 All tracks already fingerprinted!")
        return

    # Get pending tracks
    print(f"\n🔍 Loading pending tracks...")
    pending_tracks = get_pending_tracks(limit=batch_size)

    if not pending_tracks:
        print("   No tracks to process")
        return

    print(f"   Found {len(pending_tracks):,} tracks to fingerprint")
    print(f"\n🚀 Starting {num_workers} workers...")
    print(f"   Expected throughput: ~{num_workers * 15} tracks/min")

    # Progress tracking
    start_time = time.time()
    completed_count = 0
    error_count = 0

    # Process tracks in parallel (using processes to bypass GIL)
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(worker_process_track, track): track[0]
            for track in pending_tracks
        }

        # Process results as they complete
        for future in as_completed(futures):
            track_id, success, error = future.result()

            if success:
                completed_count += 1

                # Progress update every 10 tracks
                if completed_count % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = completed_count / elapsed * 60  # tracks/min
                    remaining = len(pending_tracks) - completed_count
                    eta_min = remaining / rate if rate > 0 else 0

                    print(f"   ✅ {completed_count}/{len(pending_tracks)} "
                          f"({rate:.1f} tracks/min, ETA: {eta_min:.1f} min)")
            else:
                error_count += 1
                print(f"   ❌ Track {track_id} failed: {error}")

    # Final statistics
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("📊 Final Statistics")
    print("=" * 60)
    print(f"   ✅ Successful: {completed_count:,}")
    print(f"   ❌ Errors: {error_count:,}")
    print(f"   ⏱️  Total time: {elapsed/60:.1f} minutes")
    print(f"   📈 Average rate: {completed_count/(elapsed/60):.1f} tracks/min")

    # Updated database stats
    final_stats = get_fingerprint_stats()
    print(f"\n📊 Updated Database Status:")
    print(f"   ✅ Completed: {final_stats['completed']:,} "
          f"({final_stats['completed']/final_stats['total']*100:.1f}%)")
    print(f"   ⏳ Remaining: {final_stats['pending']:,}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Parallel audio fingerprinting via gRPC")
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=4,
        help='Number of parallel workers (default: 4)'
    )
    parser.add_argument(
        '--batch-size', '-b',
        type=int,
        default=None,
        help='Max tracks to process (default: all pending)'
    )

    args = parser.parse_args()

    # Validate workers
    if args.workers < 1:
        print("❌ Error: workers must be >= 1")
        return

    if args.workers > 16:
        print("⚠️  Warning: > 16 workers may overwhelm the gRPC server")

    # Run fingerprinting
    parallel_fingerprint(
        num_workers=args.workers,
        batch_size=args.batch_size
    )


if __name__ == "__main__":
    main()

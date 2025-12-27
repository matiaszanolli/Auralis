#!/usr/bin/env python3
"""
Auralis Fingerprinting Progress Monitor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Real-time progress monitoring for library fingerprinting.

Usage:
    python monitor_fingerprinting.py          # One-time check
    python monitor_fingerprinting.py --watch   # Continuous monitoring
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from sqlalchemy import create_engine, func
    from sqlalchemy.orm import sessionmaker

    from auralis.library.models import Track, TrackFingerprint
except ImportError as e:
    print(f"❌ Error: Missing dependencies. Make sure Auralis is installed.")
    sys.exit(1)


def get_status():
    """Get current fingerprinting status."""
    db_path = str(Path.home() / '.auralis' / 'library.db')
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        total_tracks = session.query(Track).count()
        fingerprinted_count = session.query(func.count(TrackFingerprint.id)).scalar() or 0
        pending_count = total_tracks - fingerprinted_count
        progress_percent = int((fingerprinted_count / max(1, total_tracks)) * 100)

        # Calculate ETA
        # Rough estimate: 30s per track average
        estimated_remaining_seconds = int(pending_count * 30)

        # Determine status message
        if total_tracks == 0:
            status = "No tracks in library"
        elif fingerprinted_count == total_tracks:
            status = "✅ All tracks fingerprinted"
        elif fingerprinted_count == 0:
            status = "⏳ Waiting to start fingerprinting..."
        else:
            status = f"🔄 Fingerprinting in progress"

        return {
            "total_tracks": total_tracks,
            "fingerprinted_tracks": fingerprinted_count,
            "pending_tracks": pending_count,
            "progress_percent": progress_percent,
            "status": status,
            "estimated_remaining_seconds": estimated_remaining_seconds
        }
    finally:
        session.close()


def format_time(seconds):
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def print_status(data, elapsed_time=None):
    """Print status in a nice format."""
    total = data["total_tracks"]
    fingerprinted = data["fingerprinted_tracks"]
    pending = data["pending_tracks"]
    progress = data["progress_percent"]
    status = data["status"]
    eta = data["estimated_remaining_seconds"]

    # Create progress bar
    bar_width = 40
    filled = int(bar_width * progress / 100)
    bar = "█" * filled + "░" * (bar_width - filled)

    print("\n")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║         📊 AURALIS FINGERPRINTING PROGRESS MONITOR            ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Status:  {status}")
    print(f"  Progress: [{bar}] {progress}%")
    print()
    print(f"  Total tracks:        {total:>8,}")
    print(f"  Fingerprinted:       {fingerprinted:>8,}  ({progress}%)")
    print(f"  Pending:             {pending:>8,}")
    print()

    if pending > 0:
        print(f"  Estimated remaining: {format_time(eta)}")
        if elapsed_time:
            print(f"  Elapsed time:        {format_time(elapsed_time)}")
    else:
        print(f"  ✅ Fingerprinting complete!")

    print()
    print("╚════════════════════════════════════════════════════════════════╝")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor Auralis fingerprinting progress"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuous monitoring mode (updates every 10 seconds)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Update interval in seconds for --watch mode (default: 10)"
    )

    args = parser.parse_args()

    if args.watch:
        print("\n🔄 Starting continuous monitoring (Ctrl+C to stop)...")
        start_time = time.time()
        last_status = None

        try:
            while True:
                try:
                    status = get_status()
                    elapsed = int(time.time() - start_time)

                    # Only redraw if status changed
                    if status != last_status:
                        print("\033[2J")  # Clear screen
                        print_status(status, elapsed)
                        last_status = status

                    # Check if complete
                    if status["pending_tracks"] == 0:
                        print("\n✅ Fingerprinting complete!")
                        break

                    time.sleep(args.interval)
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"\n❌ Error: {e}")
                    time.sleep(args.interval)

        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped")
    else:
        # One-time check
        try:
            status = get_status()
            print_status(status)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()

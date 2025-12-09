#!/usr/bin/env python3
"""
Memory Profiling for Fingerprint Extraction

Tracks memory usage at each step to identify memory leaks.
"""

import sys
import tracemalloc
import psutil
import os
from pathlib import Path
from typing import Dict, Any

# Setup memory tracking
tracemalloc.start()

def get_memory_usage() -> Dict[str, float]:
    """Get current memory stats in MB."""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()

    return {
        'rss_mb': mem_info.rss / (1024 * 1024),  # Resident Set Size
        'vms_mb': mem_info.vms / (1024 * 1024),  # Virtual Memory Size
        'percent': process.memory_percent(),
    }

def profile_section(name: str, before: Dict[str, float], after: Dict[str, float]) -> None:
    """Print memory delta for a section."""
    delta_rss = after['rss_mb'] - before['rss_mb']
    delta_vms = after['vms_mb'] - before['vms_mb']

    print(f"\n{'='*70}")
    print(f"[{name}]")
    print(f"  RSS delta: {delta_rss:+.1f} MB (now {after['rss_mb']:.1f} MB)")
    print(f"  VMS delta: {delta_vms:+.1f} MB (now {after['vms_mb']:.1f} MB)")
    print(f"  Memory %: {after['percent']:.1f}%")

    # Top memory allocations
    current, peak = tracemalloc.get_traced_memory()
    print(f"  Traced memory: {current / (1024*1024):.1f} MB (peak: {peak / (1024*1024):.1f} MB)")

async def main():
    """Profile a single fingerprint extraction."""
    from auralis.library.manager import LibraryManager
    from auralis.library.fingerprint_extractor import FingerprintExtractor
    import asyncio
    import gc

    print("🔍 Fingerprint Memory Profiling")
    print("="*70)

    # Baseline
    baseline = get_memory_usage()
    print(f"\nBaseline memory: {baseline['rss_mb']:.1f} MB")

    # Initialize LibraryManager
    print("\n[1] Initializing LibraryManager...")
    before = get_memory_usage()
    library_manager = LibraryManager()
    after = get_memory_usage()
    profile_section("LibraryManager init", before, after)

    # Initialize FingerprintExtractor
    print("\n[2] Initializing FingerprintExtractor...")
    before = get_memory_usage()
    fingerprint_extractor = FingerprintExtractor(
        fingerprint_repository=library_manager.fingerprints
    )
    after = get_memory_usage()
    profile_section("FingerprintExtractor init", before, after)

    # Get first unfingerprinted track
    print("\n[3] Getting first track...")
    all_tracks, _ = library_manager.get_all_tracks(limit=1)
    if not all_tracks:
        print("❌ No tracks found!")
        return

    track = all_tracks[0]
    print(f"   Track: {track.id} - {track.filepath}")

    # Extract fingerprint
    print("\n[4] Extracting fingerprint (FIRST TRACK)...")
    gc.collect()
    before = get_memory_usage()
    tracemalloc.reset_peak()

    success = fingerprint_extractor.extract_and_store(track.id, track.filepath)

    after = get_memory_usage()
    profile_section("First fingerprint extraction", before, after)
    print(f"   Success: {success}")

    # After cleanup
    print("\n[5] After gc.collect()...")
    before = after
    gc.collect()
    after = get_memory_usage()
    profile_section("After gc.collect()", before, after)

    # Extract another fingerprint
    print("\n[6] Getting and extracting SECOND track...")
    all_tracks, _ = library_manager.get_all_tracks(limit=2)
    track2 = all_tracks[1] if len(all_tracks) > 1 else all_tracks[0]

    gc.collect()
    before = get_memory_usage()
    tracemalloc.reset_peak()

    success2 = fingerprint_extractor.extract_and_store(track2.id, track2.filepath)

    after = get_memory_usage()
    profile_section("Second fingerprint extraction", before, after)
    print(f"   Success: {success2}")

    # After cleanup
    print("\n[7] After gc.collect()...")
    before = after
    gc.collect()
    after = get_memory_usage()
    profile_section("After gc.collect() #2", before, after)

    # Get top memory allocations
    print("\n[8] Top Memory Allocations:")
    print("="*70)
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')

    for idx, stat in enumerate(top_stats[:10], 1):
        print(f"\n{idx}. {stat.filename}:{stat.lineno}")
        print(f"   {stat.size / (1024*1024):.1f} MB ({stat.count} allocations)")
        print(f"   {stat}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

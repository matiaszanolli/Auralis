#!/usr/bin/env python3
"""
Fingerprint extraction script for music library

Extracts fingerprints for all tracks missing them in the database.
Falls back to Python analyzer if Rust server unavailable.
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "auralis-web" / "backend"))

from auralis.library.fingerprint_extractor import FingerprintExtractor
from auralis.library.manager import LibraryManager
from auralis.utils.logging import info, warning, error, debug
import warnings


def main():
    """Run fingerprinting for missing tracks"""
    info("=== Auralis Music Database Fingerprinting ===")
    info("Starting fingerprint extraction for missing tracks")

    # Initialize components
    try:
        # Use the default ~/.auralis database location (Music/Auralis may have schema issues)
        default_db = str(Path.home() / ".auralis" / "library.db")

        # Suppress deprecation warning for LibraryManager (it's the easiest way to initialize everything)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            library_manager = LibraryManager(database_path=default_db)

        fingerprint_repo = library_manager.fingerprints

        extractor = FingerprintExtractor(
            fingerprint_repository=fingerprint_repo,
            use_sidecar_files=True,
            fingerprint_strategy="sampling",
            sampling_interval=20.0,
            use_rust_server=True  # Will fall back to Python if server unavailable
        )

        # Check Rust server availability
        if extractor._is_rust_server_available():
            info("✅ Rust fingerprinting server is available (25ms per track)")
        else:
            warning("⚠️  Rust server unavailable - using Python fallback (~2000ms per track)")
            warning("   For faster fingerprinting, ensure the Rust server is running on port 8766")

        # Extract missing fingerprints
        start_time = time.time()
        info("Extracting fingerprints for tracks without them...")
        stats = extractor.extract_missing_fingerprints()
        elapsed = time.time() - start_time

        # Report results
        info("")
        info("=== Fingerprinting Complete ===")
        info(f"Success:  {stats.get('success', 0)} tracks")
        info(f"Failed:   {stats.get('failed', 0)} tracks")
        info(f"Skipped:  {stats.get('skipped', 0)} tracks")
        info(f"Cached:   {stats.get('cached', 0)} tracks (loaded from .25d file)")
        info(f"Time:     {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")

        total = sum(stats.values())
        if total > 0:
            rate = total / elapsed if elapsed > 0 else 0
            info(f"Rate:     {rate:.2f} tracks/second")

        return 0

    except Exception as e:
        error(f"Failed to extract fingerprints: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

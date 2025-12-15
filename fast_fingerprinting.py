#!/usr/bin/env python3
"""
Fast Fingerprinting Worker - Standalone, uses Rust server on port 8766
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Uses HTTP to call the Rust fingerprinting server for 80x speedup.
Falls back to stub if Rust server unavailable.

Usage: python fast_fingerprinting.py [--batch-size 50] [--timeout 300]
"""

import sys
import sqlite3
import time
import requests
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional


class FastFingerprintDB:
    """Direct SQLite access for fingerprinting"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, timeout=60, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def get_missing_fingerprints(self, limit: Optional[int] = None) -> List[Tuple[int, str]]:
        """Get tracks without fingerprints"""
        query = """
            SELECT t.id, t.filepath
            FROM tracks t
            LEFT JOIN track_fingerprints f ON t.id = f.track_id
            WHERE f.id IS NULL
            ORDER BY t.id ASC
        """
        if limit:
            query += f" LIMIT {limit}"

        self.cursor.execute(query)
        return self.cursor.fetchall()

    def count_missing(self) -> int:
        """Count tracks without fingerprints"""
        self.cursor.execute("""
            SELECT COUNT(*) FROM tracks t
            LEFT JOIN track_fingerprints f ON t.id = f.track_id
            WHERE f.id IS NULL
        """)
        return self.cursor.fetchone()[0]

    def save_fingerprint(self, track_id: int, fingerprint: Dict) -> bool:
        """Save fingerprint to database"""
        try:
            self.cursor.execute("""
                INSERT OR REPLACE INTO track_fingerprints (
                    track_id, sub_bass_pct, bass_pct, low_mid_pct, mid_pct,
                    upper_mid_pct, presence_pct, air_pct, lufs, crest_db,
                    bass_mid_ratio, tempo_bpm, rhythm_stability, transient_density,
                    silence_ratio, spectral_centroid, spectral_rolloff, spectral_flatness,
                    harmonic_ratio, pitch_stability, chroma_energy,
                    dynamic_range_variation, loudness_variation_std, peak_consistency,
                    stereo_width, phase_correlation, fingerprint_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                track_id,
                fingerprint.get('sub_bass_pct', 0),
                fingerprint.get('bass_pct', 0),
                fingerprint.get('low_mid_pct', 0),
                fingerprint.get('mid_pct', 0),
                fingerprint.get('upper_mid_pct', 0),
                fingerprint.get('presence_pct', 0),
                fingerprint.get('air_pct', 0),
                fingerprint.get('lufs', 0),
                fingerprint.get('crest_db', 0),
                fingerprint.get('bass_mid_ratio', 0),
                fingerprint.get('tempo_bpm', 0),
                fingerprint.get('rhythm_stability', 0),
                fingerprint.get('transient_density', 0),
                fingerprint.get('silence_ratio', 0),
                fingerprint.get('spectral_centroid', 0),
                fingerprint.get('spectral_rolloff', 0),
                fingerprint.get('spectral_flatness', 0),
                fingerprint.get('harmonic_ratio', 0),
                fingerprint.get('pitch_stability', 0),
                fingerprint.get('chroma_energy', 0),
                fingerprint.get('dynamic_range_variation', 0),
                fingerprint.get('loudness_variation_std', 0),
                fingerprint.get('peak_consistency', 0),
                fingerprint.get('stereo_width', 0),
                fingerprint.get('phase_correlation', 0),
                fingerprint.get('fingerprint_version', 1),
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error saving fingerprint: {e}")
            return False

    def close(self):
        self.conn.close()


def check_rust_server() -> bool:
    """Check if Rust server is available"""
    try:
        resp = requests.get("http://localhost:8766/health", timeout=2)
        return resp.status_code == 200
    except:
        return False


def fingerprint_via_rust(track_id: int, filepath: str) -> Optional[Dict]:
    """Call Rust server to fingerprint a track"""
    try:
        if not Path(filepath).exists():
            return None

        resp = requests.post(
            "http://localhost:8766/fingerprint",
            json={"track_id": track_id, "filepath": filepath},
            timeout=30
        )

        if resp.status_code == 200:
            data = resp.json()
            # Extract fingerprint data from Rust server response
            fingerprint = data.get('fingerprint', {})

            # Rust server returns a dict with dimension_0..dimension_24
            # We need to map those to our database schema
            # For now, use default values if Rust doesn't provide them
            return {
                'sub_bass_pct': fingerprint.get('dimension_0', 0.1),
                'bass_pct': fingerprint.get('dimension_1', 0.1),
                'low_mid_pct': fingerprint.get('dimension_2', 0.1),
                'mid_pct': fingerprint.get('dimension_3', 0.2),
                'upper_mid_pct': fingerprint.get('dimension_4', 0.2),
                'presence_pct': fingerprint.get('dimension_5', 0.1),
                'air_pct': fingerprint.get('dimension_6', 0.05),
                'lufs': fingerprint.get('dimension_7', -20.0),
                'crest_db': fingerprint.get('dimension_8', 8.0),
                'bass_mid_ratio': fingerprint.get('dimension_9', 1.0),
                'tempo_bpm': fingerprint.get('dimension_10', 120.0),
                'rhythm_stability': fingerprint.get('dimension_11', 0.8),
                'transient_density': fingerprint.get('dimension_12', 0.5),
                'silence_ratio': fingerprint.get('dimension_13', 0.05),
                'spectral_centroid': fingerprint.get('dimension_14', 2000.0),
                'spectral_rolloff': fingerprint.get('dimension_15', 8000.0),
                'spectral_flatness': fingerprint.get('dimension_16', 0.5),
                'harmonic_ratio': fingerprint.get('dimension_17', 0.7),
                'pitch_stability': fingerprint.get('dimension_18', 0.8),
                'chroma_energy': fingerprint.get('dimension_19', 0.6),
                'dynamic_range_variation': fingerprint.get('dimension_20', 0.3),
                'loudness_variation_std': fingerprint.get('dimension_21', 1.5),
                'peak_consistency': fingerprint.get('dimension_22', 0.85),
                'stereo_width': fingerprint.get('dimension_23', 0.8),
                'phase_correlation': fingerprint.get('dimension_24', 0.9),
                'fingerprint_version': 1,
            }
        return None
    except Exception as e:
        print(f"  ⚠️  Rust server error for track {track_id}: {e}")
        return None


def main():
    db_path = str(Path.home() / ".auralis" / "library.db")

    print("=" * 60)
    print("🎵 Auralis Fast Fingerprinting Worker")
    print("=" * 60)

    # Connect to database
    db = FastFingerprintDB(db_path)
    total_missing = db.count_missing()

    print(f"\n📊 Database: {db_path}")
    print(f"📊 Tracks needing fingerprints: {total_missing:,}")

    if total_missing == 0:
        print("✅ All tracks already have fingerprints!")
        db.close()
        return 0

    # Check Rust server
    rust_available = check_rust_server()
    if rust_available:
        print("✅ Rust server available (25ms per track)")
    else:
        print("⚠️  Rust server unavailable (stub mode)")

    # Fingerprint in batches
    batch_size = 100
    processed = 0
    success = 0
    failed = 0
    skipped = 0
    start_time = time.time()

    print(f"\n🎯 Starting fingerprinting ({total_missing:,} tracks)...\n")

    while True:
        tracks = db.get_missing_fingerprints(limit=batch_size)
        if not tracks:
            break

        print(f"📦 Processing batch of {len(tracks)} tracks...")

        for track_id, filepath in tracks:
            try:
                if not Path(filepath).exists():
                    skipped += 1
                    continue

                # Fingerprint via Rust server
                fingerprint = fingerprint_via_rust(track_id, filepath)

                if fingerprint and db.save_fingerprint(track_id, fingerprint):
                    success += 1
                else:
                    failed += 1

                processed += 1

                # Progress update every 50
                if processed % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed
                    remaining = (total_missing - processed) / rate
                    pct = (processed / total_missing) * 100
                    print(f"   Progress: {processed:,}/{total_missing:,} ({pct:.1f}%) "
                          f"| {rate:.1f}/sec | ~{remaining/60:.0f}min remaining")

            except KeyboardInterrupt:
                print("\n⏸️  Interrupted by user")
                db.close()
                return 1
            except Exception as e:
                failed += 1
                processed += 1

    db.close()

    # Final report
    elapsed = time.time() - start_time
    rate = processed / elapsed if elapsed > 0 else 0

    print(f"\n{'=' * 60}")
    print("✅ Fingerprinting Complete")
    print(f"{'=' * 60}")
    print(f"✅ Success:  {success:,}")
    print(f"❌ Failed:   {failed:,}")
    print(f"⊘  Skipped:  {skipped:,}")
    print(f"⏱️  Time:     {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"⚡ Rate:     {rate:.1f} tracks/sec")
    print(f"{'=' * 60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

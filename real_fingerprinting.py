#!/usr/bin/env python3
"""
Real Fingerprinting - Uses actual Auralis fingerprinting code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Properly computes 25D audio fingerprints using the Auralis analysis engine.
Works around SQLAlchemy ORM issues by using direct database access.

Usage: python real_fingerprinting.py [--batch-size 50]
"""

import sys
import sqlite3
import time
from pathlib import Path
from typing import List, Tuple, Dict, Optional

# Add to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "auralis-web" / "backend"))

try:
    from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
    from auralis.utils.logging import info, warning, error
    AURALIS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Auralis import error: {e}")
    AURALIS_AVAILABLE = False


class RealFingerprintDB:
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
                float(fingerprint.get('sub_bass_pct', 0)),
                float(fingerprint.get('bass_pct', 0)),
                float(fingerprint.get('low_mid_pct', 0)),
                float(fingerprint.get('mid_pct', 0)),
                float(fingerprint.get('upper_mid_pct', 0)),
                float(fingerprint.get('presence_pct', 0)),
                float(fingerprint.get('air_pct', 0)),
                float(fingerprint.get('lufs', 0)),
                float(fingerprint.get('crest_db', 0)),
                float(fingerprint.get('bass_mid_ratio', 0)),
                float(fingerprint.get('tempo_bpm', 0)),
                float(fingerprint.get('rhythm_stability', 0)),
                float(fingerprint.get('transient_density', 0)),
                float(fingerprint.get('silence_ratio', 0)),
                float(fingerprint.get('spectral_centroid', 0)),
                float(fingerprint.get('spectral_rolloff', 0)),
                float(fingerprint.get('spectral_flatness', 0)),
                float(fingerprint.get('harmonic_ratio', 0)),
                float(fingerprint.get('pitch_stability', 0)),
                float(fingerprint.get('chroma_energy', 0)),
                float(fingerprint.get('dynamic_range_variation', 0)),
                float(fingerprint.get('loudness_variation_std', 0)),
                float(fingerprint.get('peak_consistency', 0)),
                float(fingerprint.get('stereo_width', 0)),
                float(fingerprint.get('phase_correlation', 0)),
                fingerprint.get('fingerprint_version', 1),
            ))
            self.conn.commit()
            return True
        except Exception as e:
            error(f"Error saving fingerprint for track {track_id}: {e}")
            return False

    def close(self):
        self.conn.close()


def compute_fingerprint_auralis(track_id: int, filepath: str) -> Optional[Dict]:
    """Use Auralis fingerprinting analyzer to compute real fingerprints"""
    if not AURALIS_AVAILABLE:
        return None

    try:
        analyzer = AudioFingerprintAnalyzer()
        fingerprint_dict = analyzer.analyze(str(filepath))

        if fingerprint_dict:
            # Convert analyzer output to database schema
            return {
                'sub_bass_pct': fingerprint_dict.get('sub_bass_pct', 0),
                'bass_pct': fingerprint_dict.get('bass_pct', 0),
                'low_mid_pct': fingerprint_dict.get('low_mid_pct', 0),
                'mid_pct': fingerprint_dict.get('mid_pct', 0),
                'upper_mid_pct': fingerprint_dict.get('upper_mid_pct', 0),
                'presence_pct': fingerprint_dict.get('presence_pct', 0),
                'air_pct': fingerprint_dict.get('air_pct', 0),
                'lufs': fingerprint_dict.get('lufs', 0),
                'crest_db': fingerprint_dict.get('crest_db', 0),
                'bass_mid_ratio': fingerprint_dict.get('bass_mid_ratio', 0),
                'tempo_bpm': fingerprint_dict.get('tempo_bpm', 0),
                'rhythm_stability': fingerprint_dict.get('rhythm_stability', 0),
                'transient_density': fingerprint_dict.get('transient_density', 0),
                'silence_ratio': fingerprint_dict.get('silence_ratio', 0),
                'spectral_centroid': fingerprint_dict.get('spectral_centroid', 0),
                'spectral_rolloff': fingerprint_dict.get('spectral_rolloff', 0),
                'spectral_flatness': fingerprint_dict.get('spectral_flatness', 0),
                'harmonic_ratio': fingerprint_dict.get('harmonic_ratio', 0),
                'pitch_stability': fingerprint_dict.get('pitch_stability', 0),
                'chroma_energy': fingerprint_dict.get('chroma_energy', 0),
                'dynamic_range_variation': fingerprint_dict.get('dynamic_range_variation', 0),
                'loudness_variation_std': fingerprint_dict.get('loudness_variation_std', 0),
                'peak_consistency': fingerprint_dict.get('peak_consistency', 0),
                'stereo_width': fingerprint_dict.get('stereo_width', 0),
                'phase_correlation': fingerprint_dict.get('phase_correlation', 0),
                'fingerprint_version': 1,
            }
        return None
    except Exception as e:
        error(f"Fingerprinting error for track {track_id}: {e}")
        return None


def main():
    db_path = str(Path.home() / ".auralis" / "library.db")

    print("=" * 70)
    print("🎵 Auralis Real Fingerprinting - Using Actual Audio Analysis")
    print("=" * 70)

    if not AURALIS_AVAILABLE:
        print("\n❌ ERROR: Auralis fingerprinting module not available!")
        print("   This is expected if there are import issues.")
        print("\n   This script requires the full Auralis analysis engine.")
        return 1

    # Connect to database
    db = RealFingerprintDB(db_path)
    total_missing = db.count_missing()

    print(f"\n📊 Database: {db_path}")
    print(f"📊 Tracks needing fingerprints: {total_missing:,}")

    if total_missing == 0:
        print("✅ All tracks already have fingerprints!")
        db.close()
        return 0

    # Fingerprint in batches
    batch_size = 50
    processed = 0
    success = 0
    failed = 0
    skipped = 0
    start_time = time.time()

    print(f"\n🎯 Starting real fingerprinting ({total_missing:,} tracks)...\n")

    while True:
        tracks = db.get_missing_fingerprints(limit=batch_size)
        if not tracks:
            break

        print(f"📦 Processing batch of {len(tracks)} tracks...")

        for track_id, filepath in tracks:
            try:
                if not Path(filepath).exists():
                    skipped += 1
                    processed += 1
                    continue

                # Compute real fingerprint using Auralis
                fingerprint = compute_fingerprint_auralis(track_id, filepath)

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
                    est_hours = remaining / 3600
                    print(f"   Progress: {processed:,}/{total_missing:,} ({pct:.1f}%) "
                          f"| {rate:.2f}/sec | ~{est_hours:.1f}h remaining")

            except KeyboardInterrupt:
                print("\n⏸️  Interrupted by user")
                db.close()
                return 1
            except Exception as e:
                error(f"Unexpected error for track {track_id}: {e}")
                failed += 1
                processed += 1

    db.close()

    # Final report
    elapsed = time.time() - start_time
    rate = processed / elapsed if elapsed > 0 else 0

    print(f"\n{'=' * 70}")
    print("✅ Fingerprinting Complete")
    print(f"{'=' * 70}")
    print(f"✅ Success:  {success:,}")
    print(f"❌ Failed:   {failed:,}")
    print(f"⊘  Skipped:  {skipped:,}")
    print(f"⏱️  Time:     {elapsed:.0f}s ({elapsed/3600:.2f}h)")
    print(f"⚡ Rate:     {rate:.2f} tracks/sec (~{elapsed/processed if processed > 0 else 0:.1f}s per track)")
    print(f"{'=' * 70}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

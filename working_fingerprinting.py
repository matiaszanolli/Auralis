#!/usr/bin/env python3
"""
Working Fingerprinting - Hybrid approach that actually works
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Uses real Auralis fingerprinting (with Rust DSP) but saves via direct SQLite.
Bypasses the SQLAlchemy ORM metadata issue.

Usage: python working_fingerprinting.py [--limit 100]
"""

import sys
import sqlite3
import time
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Optional

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

# Import fingerprinting analyzer directly
try:
    from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
    ANALYZER_AVAILABLE = True
except ImportError as e:
    print(f"❌ Cannot import AudioFingerprintAnalyzer: {e}")
    ANALYZER_AVAILABLE = False


class DirectDB:
    """Direct SQLite access - no ORM"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, timeout=60, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def get_tracks_needing_fingerprints(self, limit: Optional[int] = None) -> List[Tuple[int, str]]:
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
        """Count tracks missing fingerprints"""
        self.cursor.execute("""
            SELECT COUNT(*) FROM tracks t
            LEFT JOIN track_fingerprints f ON t.id = f.track_id
            WHERE f.id IS NULL
        """)
        return self.cursor.fetchone()[0]

    def save_fingerprint(self, track_id: int, fp_data: Dict) -> bool:
        """Save fingerprint directly via SQL"""
        try:
            # Check if already exists
            self.cursor.execute("SELECT id FROM track_fingerprints WHERE track_id = ?", (track_id,))
            exists = self.cursor.fetchone()

            if exists:
                # Update existing
                self.cursor.execute("""
                    UPDATE track_fingerprints SET
                        sub_bass_pct = ?, bass_pct = ?, low_mid_pct = ?, mid_pct = ?,
                        upper_mid_pct = ?, presence_pct = ?, air_pct = ?,
                        lufs = ?, crest_db = ?, bass_mid_ratio = ?,
                        tempo_bpm = ?, rhythm_stability = ?, transient_density = ?, silence_ratio = ?,
                        spectral_centroid = ?, spectral_rolloff = ?, spectral_flatness = ?,
                        harmonic_ratio = ?, pitch_stability = ?, chroma_energy = ?,
                        dynamic_range_variation = ?, loudness_variation_std = ?, peak_consistency = ?,
                        stereo_width = ?, phase_correlation = ?, fingerprint_version = ?
                    WHERE track_id = ?
                """, (
                    fp_data['sub_bass_pct'], fp_data['bass_pct'], fp_data['low_mid_pct'], fp_data['mid_pct'],
                    fp_data['upper_mid_pct'], fp_data['presence_pct'], fp_data['air_pct'],
                    fp_data['lufs'], fp_data['crest_db'], fp_data['bass_mid_ratio'],
                    fp_data['tempo_bpm'], fp_data['rhythm_stability'], fp_data['transient_density'], fp_data['silence_ratio'],
                    fp_data['spectral_centroid'], fp_data['spectral_rolloff'], fp_data['spectral_flatness'],
                    fp_data['harmonic_ratio'], fp_data['pitch_stability'], fp_data['chroma_energy'],
                    fp_data['dynamic_range_variation'], fp_data['loudness_variation_std'], fp_data['peak_consistency'],
                    fp_data['stereo_width'], fp_data['phase_correlation'], fp_data.get('fingerprint_version', 1),
                    track_id
                ))
            else:
                # Insert new
                self.cursor.execute("""
                    INSERT INTO track_fingerprints (
                        track_id, sub_bass_pct, bass_pct, low_mid_pct, mid_pct,
                        upper_mid_pct, presence_pct, air_pct, lufs, crest_db,
                        bass_mid_ratio, tempo_bpm, rhythm_stability, transient_density, silence_ratio,
                        spectral_centroid, spectral_rolloff, spectral_flatness,
                        harmonic_ratio, pitch_stability, chroma_energy,
                        dynamic_range_variation, loudness_variation_std, peak_consistency,
                        stereo_width, phase_correlation, fingerprint_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    track_id,
                    fp_data['sub_bass_pct'], fp_data['bass_pct'], fp_data['low_mid_pct'], fp_data['mid_pct'],
                    fp_data['upper_mid_pct'], fp_data['presence_pct'], fp_data['air_pct'],
                    fp_data['lufs'], fp_data['crest_db'], fp_data['bass_mid_ratio'],
                    fp_data['tempo_bpm'], fp_data['rhythm_stability'], fp_data['transient_density'], fp_data['silence_ratio'],
                    fp_data['spectral_centroid'], fp_data['spectral_rolloff'], fp_data['spectral_flatness'],
                    fp_data['harmonic_ratio'], fp_data['pitch_stability'], fp_data['chroma_energy'],
                    fp_data['dynamic_range_variation'], fp_data['loudness_variation_std'], fp_data['peak_consistency'],
                    fp_data['stereo_width'], fp_data['phase_correlation'], fp_data.get('fingerprint_version', 1)
                ))

            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Save error for track {track_id}: {e}")
            self.conn.rollback()
            return False

    def close(self):
        self.conn.close()


def compute_fingerprint(track_id: int, filepath: str, analyzer: AudioFingerprintAnalyzer) -> Optional[Dict]:
    """Compute real fingerprint using Auralis analyzer"""
    try:
        if not Path(filepath).exists():
            return None

        # Load audio file first
        import librosa
        audio, sr = librosa.load(str(filepath), sr=None, mono=False)

        # Use Auralis analyzer (which uses Rust DSP internally)
        result = analyzer.analyze(audio, sr)

        if result and isinstance(result, dict):
            # Analyzer returns a dict with all 25 dimensions
            return result

        return None
    except Exception as e:
        print(f"  ⚠️  Fingerprint error for track {track_id}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Working fingerprinting with real Auralis code')
    parser.add_argument('--limit', type=int, help='Limit number of tracks to process')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size')
    args = parser.parse_args()

    if not ANALYZER_AVAILABLE:
        print("\n❌ ERROR: AudioFingerprintAnalyzer not available!")
        print("   Cannot proceed without the Auralis fingerprinting module.\n")
        return 1

    db_path = str(Path.home() / ".auralis" / "library.db")

    print("=" * 70)
    print("🎵 Auralis Working Fingerprinting - Real Audio Analysis + Direct SQL")
    print("=" * 70)

    # Initialize
    db = DirectDB(db_path)
    analyzer = AudioFingerprintAnalyzer()

    total_missing = db.count_missing()
    process_limit = args.limit if args.limit else total_missing

    print(f"\n📊 Database: {db_path}")
    print(f"📊 Tracks missing fingerprints: {total_missing:,}")
    print(f"📊 Will process: {min(process_limit, total_missing):,}")

    if total_missing == 0:
        print("✅ All tracks already have fingerprints!")
        db.close()
        return 0

    # Process
    success = 0
    failed = 0
    skipped = 0
    processed = 0
    start_time = time.time()

    print(f"\n🎯 Starting fingerprinting...\n")

    while processed < process_limit:
        batch = db.get_tracks_needing_fingerprints(limit=args.batch_size)
        if not batch:
            break

        print(f"📦 Processing batch of {len(batch)} tracks...")

        for track_id, filepath in batch:
            if processed >= process_limit:
                break

            try:
                if not Path(filepath).exists():
                    skipped += 1
                    processed += 1
                    continue

                # Compute real fingerprint
                fp_data = compute_fingerprint(track_id, filepath, analyzer)

                if fp_data and db.save_fingerprint(track_id, fp_data):
                    success += 1
                    if success % 10 == 0:
                        print(f"  ✅ {success} tracks fingerprinted...")
                else:
                    failed += 1
                    if failed % 10 == 0:
                        print(f"  ❌ {failed} failures so far...")

                processed += 1

                # Progress every 50
                if processed % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed
                    remaining = (process_limit - processed) / rate if rate > 0 else 0
                    pct = (processed / process_limit) * 100
                    print(f"   Progress: {processed:,}/{process_limit:,} ({pct:.1f}%) "
                          f"| {rate:.2f}/sec | ~{remaining/60:.1f}min remaining")

            except KeyboardInterrupt:
                print("\n⏸️  Interrupted by user")
                db.close()
                return 1
            except Exception as e:
                print(f"❌ Unexpected error for track {track_id}: {e}")
                failed += 1
                processed += 1

    db.close()

    # Final report
    elapsed = time.time() - start_time
    rate = processed / elapsed if elapsed > 0 else 0

    print(f"\n{'=' * 70}")
    print("✅ Fingerprinting Session Complete")
    print(f"{'=' * 70}")
    print(f"✅ Success:  {success:,}")
    print(f"❌ Failed:   {failed:,}")
    print(f"⊘  Skipped:  {skipped:,}")
    print(f"⏱️  Time:     {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"⚡ Rate:     {rate:.2f} tracks/sec ({elapsed/processed if processed > 0 else 0:.1f}s per track)")
    print(f"{'=' * 70}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

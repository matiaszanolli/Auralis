"""
Phase 7B: Performance Profiling at Scale (100+ Track Library)

Tests sampling strategy performance on large-scale library processing:
- Benchmarks processing speed (tracks/minute, throughput)
- Memory profiling during bulk operations
- Identifies bottlenecks in large batch processing
- Validates library scaling estimates

Processes all available FLAC files from music library to validate
production readiness at realistic scale.
"""

import numpy as np
import time
from pathlib import Path
import sys
import gc
from collections import defaultdict
import psutil
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
from auralis.io.unified_loader import load_audio


class PerformanceProfiler:
    """Profile sampling strategy at scale."""

    def __init__(self):
        self.results = []
        self.sr = 44100
        self.process = psutil.Process(os.getpid())
        self.initial_memory = 0

    def test_track_sampling(self, track_path: Path) -> dict:
        """Test a single track with sampling strategy."""
        try:
            # Memory before
            gc.collect()
            mem_before = self.process.memory_info().rss / (1024 * 1024)  # MB

            audio, _ = load_audio(str(track_path), target_sample_rate=self.sr)

            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)

            audio = audio.astype(np.float64)
            duration_s = len(audio) / self.sr

            # Sampling analysis
            analyzer = AudioFingerprintAnalyzer(
                fingerprint_strategy="sampling",
                sampling_interval=20.0
            )

            start = time.perf_counter()
            features = analyzer.analyze(audio, self.sr)
            analysis_time = time.perf_counter() - start

            # Memory after
            mem_after = self.process.memory_info().rss / (1024 * 1024)  # MB
            mem_used = mem_after - mem_before

            del audio, analyzer, features
            gc.collect()

            # Calculate throughput
            throughput = duration_s / analysis_time if analysis_time > 0 else 0

            return {
                "track": track_path.stem,
                "duration_s": duration_s,
                "time": analysis_time,
                "throughput": throughput,
                "memory_used_mb": max(0, mem_used),
                "error": None,
            }

        except Exception as e:
            return {
                "track": track_path.stem,
                "duration_s": 0,
                "error": str(e)[:80],
            }

    def run_library_scan(self, limit: int = None) -> list:
        """Scan entire music library and process all FLAC files."""
        music_root = Path("/mnt/Musica/Musica")

        if not music_root.exists():
            print("⚠️  Music library not found")
            return []

        # Find all FLAC files recursively
        print(f"\n🔍 Scanning library for FLAC files...")
        all_flacs = list(music_root.rglob("*.flac"))

        if limit:
            all_flacs = all_flacs[:limit]

        print(f"   Found {len(all_flacs)} FLAC files to process")

        results = []
        failed = 0
        start_time = time.perf_counter()

        print(f"\n📊 PROCESSING {len(all_flacs)} TRACKS")
        print("-" * 110)
        print(f"{'#':<5} {'Track':<45} {'Duration':<12} {'Time':<10} {'Throughput':<12} {'Memory':<10}")
        print("-" * 110)

        for i, track_path in enumerate(all_flacs, 1):
            result = self.test_track_sampling(track_path)
            results.append(result)

            if "error" in result and result["error"]:
                print(f"{i:<5} {result['track']:<45} ERROR: {result['error']}")
                failed += 1
            else:
                print(
                    f"{i:<5} {result['track']:<45} {result['duration_s']:>7.1f}s    "
                    f"{result['time']:>8.3f}s  {result['throughput']:>10.1f}x realtime  "
                    f"{result['memory_used_mb']:>7.1f}MB"
                )

            # Progress and memory status every 10 tracks
            if i % 10 == 0:
                current_memory = self.process.memory_info().rss / (1024 * 1024)
                elapsed = time.perf_counter() - start_time
                print(f"   [Progress: {i}/{len(all_flacs)} | Memory: {current_memory:.0f}MB | Elapsed: {elapsed:.1f}s]")

        total_time = time.perf_counter() - start_time

        print("\n" + "=" * 110)
        print("LIBRARY PERFORMANCE SUMMARY")
        print("=" * 110)

        valid_results = [r for r in results if "error" not in r or not r["error"]]

        if valid_results:
            total_duration = sum(r["duration_s"] for r in valid_results)
            total_analysis_time = sum(r["time"] for r in valid_results)
            avg_throughput = np.mean([r["throughput"] for r in valid_results])
            avg_memory = np.mean([r["memory_used_mb"] for r in valid_results])

            print(f"\n✅ Successfully processed {len(valid_results)} tracks")
            print(f"   Failed: {failed} tracks")
            print(f"   Total audio duration: {total_duration:.1f}s ({total_duration/3600:.2f} hours)")
            print(f"   Total processing time: {total_analysis_time:.2f}s ({total_analysis_time/60:.2f} minutes)")
            print(f"   Average throughput: {avg_throughput:.1f}x realtime")
            print(f"   Average memory per track: {avg_memory:.1f}MB")
            print(f"   Total wall-clock time: {total_time:.2f}s")

            # Scaling calculations
            print(f"\n" + "-" * 110)
            print("LIBRARY SCALING ESTIMATES (based on actual measurements)")
            print("-" * 110)

            processing_rate = total_duration / total_analysis_time  # x realtime
            tracks_per_second = len(valid_results) / total_analysis_time
            seconds_per_track = total_analysis_time / len(valid_results)

            print(f"\nCurrent Library Statistics:")
            print(f"  Tracks processed: {len(valid_results)}")
            print(f"  Total duration: {total_duration:.1f}s ({total_duration/3600:.2f} hours)")
            print(f"  Processing rate: {processing_rate:.1f}x realtime")
            print(f"  Per-track average: {seconds_per_track:.3f}s/track")
            print(f"  Processing speed: {tracks_per_second:.2f} tracks/second")

            # Estimate for standard library sizes
            estimates = [
                (100, "100-track library"),
                (500, "500-track library"),
                (1000, "1000-track library (production target)"),
                (5000, "5000-track library (comprehensive)"),
            ]

            print(f"\nScaling to Standard Library Sizes:")
            for n_tracks, label in estimates:
                # Assume average track duration from this sample
                avg_track_duration = total_duration / len(valid_results)
                est_total_duration = n_tracks * avg_track_duration
                est_processing_time = est_total_duration / processing_rate

                if est_processing_time < 60:
                    time_str = f"{est_processing_time:.1f}s"
                elif est_processing_time < 3600:
                    time_str = f"{est_processing_time/60:.1f}m"
                else:
                    time_str = f"{est_processing_time/3600:.1f}h"

                print(f"  {label:<40} ~{time_str:>6} ({est_total_duration/3600:.1f} hrs audio)")

            # Performance metrics
            print(f"\n" + "-" * 110)
            print("PERFORMANCE METRICS")
            print("-" * 110)

            throughputs = [r["throughput"] for r in valid_results]
            print(f"\nThroughput Distribution:")
            print(f"  Minimum: {min(throughputs):.1f}x realtime")
            print(f"  Average: {avg_throughput:.1f}x realtime")
            print(f"  Maximum: {max(throughputs):.1f}x realtime")
            print(f"  Std Dev: {np.std(throughputs):.1f}x")

            # Duration vs throughput correlation
            durations = [r["duration_s"] for r in valid_results]
            correlation = np.corrcoef(durations, throughputs)[0, 1]
            print(f"\nDuration vs Throughput Correlation: {correlation:.3f}")
            if abs(correlation) < 0.3:
                print(f"  → Throughput is stable regardless of track length")
            elif correlation < 0:
                print(f"  → Longer tracks process slightly faster (less overhead per hour)")
            else:
                print(f"  → Shorter tracks process faster (faster to initialize/finalize)")

            # Memory profile
            print(f"\nMemory Usage Profile:")
            print(f"  Average per track: {avg_memory:.1f}MB")
            print(f"  Peak during session: {self.process.memory_info().rss / (1024 * 1024):.0f}MB")
            print(f"  Estimated for 1000 tracks: {(1000 * seconds_per_track * avg_memory / 60):.0f}MB")

        print("\n" + "=" * 110 + "\n")
        return valid_results

    def generate_report(self, results: list):
        """Generate detailed performance report."""
        if not results:
            return

        print("\n" + "=" * 110)
        print("DETAILED PERFORMANCE REPORT")
        print("=" * 110)

        valid_results = [r for r in results if "error" not in r or not r["error"]]

        # By duration ranges
        print(f"\nPerformance by Track Duration:")
        print("-" * 110)

        ranges = [
            (0, 120, "Short (< 2 min)"),
            (120, 300, "Medium (2-5 min)"),
            (300, 600, "Long (5-10 min)"),
            (600, float('inf'), "Very Long (> 10 min)"),
        ]

        for min_dur, max_dur, label in ranges:
            range_results = [r for r in valid_results if min_dur <= r["duration_s"] < max_dur]
            if range_results:
                avg_throughput = np.mean([r["throughput"] for r in range_results])
                avg_time = np.mean([r["time"] for r in range_results])
                print(f"  {label:<25} {len(range_results):>3} tracks | "
                      f"avg throughput: {avg_throughput:>6.1f}x | "
                      f"avg time: {avg_time:>7.3f}s")

        # Slowest and fastest tracks
        print(f"\nTop 5 Slowest Tracks (lowest throughput):")
        print("-" * 110)
        slowest = sorted(valid_results, key=lambda r: r["throughput"])[:5]
        for i, result in enumerate(slowest, 1):
            print(f"  {i}. {result['track']:<40} {result['duration_s']:>7.1f}s | "
                  f"{result['time']:>7.3f}s | {result['throughput']:>6.1f}x realtime")

        print(f"\nTop 5 Fastest Tracks (highest throughput):")
        print("-" * 110)
        fastest = sorted(valid_results, key=lambda r: r["throughput"], reverse=True)[:5]
        for i, result in enumerate(fastest, 1):
            print(f"  {i}. {result['track']:<40} {result['duration_s']:>7.1f}s | "
                  f"{result['time']:>7.3f}s | {result['throughput']:>6.1f}x realtime")


if __name__ == "__main__":
    profiler = PerformanceProfiler()
    results = profiler.run_library_scan(limit=100)  # Limit to 100 tracks for reasonable runtime
    profiler.generate_report(results)

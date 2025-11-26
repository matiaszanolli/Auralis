"""
Benchmark: Sampled vs Full-Track Harmonic Analysis

Compares time-domain sampling strategy against full-track analysis on Pearl Jam's "Ten".

Test Scenarios:
- Different sampling intervals (no sampling, 5s chunks every 10s, 5s chunks every 15s, etc.)
- Accuracy comparison (feature correlation with full-track)
- Performance improvement (throughput gain)
- Album-wide metrics

Sampling Strategy:
- Extract non-overlapping 5-second chunks at regular intervals
- Analyze each chunk independently with Rust DSP
- Aggregate results via averaging
- Expected speedup: 2-5x depending on track length
"""

import numpy as np
import time
from pathlib import Path
import sys
import gc
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.fingerprint.harmonic_analyzer import HarmonicAnalyzer
from auralis.analysis.fingerprint.harmonic_analyzer_sampled import SampledHarmonicAnalyzer
from auralis.io.unified_loader import load_audio


def benchmark_track_fulltrack(track_path: Path, sr: int = 44100) -> Dict:
    """Benchmark a single track with full-track analysis."""
    track_name = track_path.stem

    try:
        # Load audio (convert to mono immediately)
        audio, loaded_sr = load_audio(str(track_path), target_sample_rate=sr)

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        audio = audio.astype(np.float64)
        duration_s = len(audio) / sr

        # Full-track analysis
        analyzer = HarmonicAnalyzer()

        start = time.perf_counter()
        features_full = analyzer.analyze(audio, sr)
        time_full = time.perf_counter() - start

        del audio
        del analyzer
        gc.collect()

        return {
            "track": track_name,
            "duration_s": duration_s,
            "time_full": time_full,
            "features_full": features_full,
            "error": None,
        }
    except Exception as e:
        gc.collect()
        return {
            "track": track_name,
            "duration_s": 0,
            "time_full": None,
            "features_full": None,
            "error": str(e),
        }


def benchmark_track_sampled(track_path: Path, sr: int = 44100,
                           chunk_duration: float = 5.0,
                           interval_duration: float = 10.0) -> Dict:
    """Benchmark a single track with sampled analysis."""
    track_name = track_path.stem

    try:
        # Load audio (convert to mono immediately)
        audio, loaded_sr = load_audio(str(track_path), target_sample_rate=sr)

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        audio = audio.astype(np.float64)
        duration_s = len(audio) / sr

        # Sampled analysis
        analyzer = SampledHarmonicAnalyzer(
            chunk_duration=chunk_duration,
            interval_duration=interval_duration
        )

        start = time.perf_counter()
        features_sampled = analyzer.analyze(audio, sr)
        time_sampled = time.perf_counter() - start

        del audio
        del analyzer
        gc.collect()

        return {
            "track": track_name,
            "duration_s": duration_s,
            "time_sampled": time_sampled,
            "features_sampled": features_sampled,
            "error": None,
        }
    except Exception as e:
        gc.collect()
        return {
            "track": track_name,
            "duration_s": 0,
            "time_sampled": None,
            "features_sampled": None,
            "error": str(e),
        }


def calculate_feature_correlation(features_full: Dict, features_sampled: Dict) -> float:
    """
    Calculate correlation between full-track and sampled features.

    Returns: Correlation coefficient (0-1, 1 = identical)
    """
    if not features_full or not features_sampled:
        return 0.0

    keys = ['harmonic_ratio', 'pitch_stability', 'chroma_energy']
    full_values = np.array([features_full.get(k, 0.5) for k in keys])
    sampled_values = np.array([features_sampled.get(k, 0.5) for k in keys])

    # Calculate Pearson correlation
    try:
        correlation = np.corrcoef(full_values, sampled_values)[0, 1]
        if np.isnan(correlation):
            correlation = 1.0  # Identical if all same value
        return correlation
    except:
        return 0.0


def calculate_feature_mae(features_full: Dict, features_sampled: Dict) -> float:
    """Calculate mean absolute error between features."""
    if not features_full or not features_sampled:
        return 0.0

    keys = ['harmonic_ratio', 'pitch_stability', 'chroma_energy']
    full_values = np.array([features_full.get(k, 0.5) for k in keys])
    sampled_values = np.array([features_sampled.get(k, 0.5) for k in keys])

    mae = np.mean(np.abs(full_values - sampled_values))
    return mae


class SamplingBenchmark:
    """Comprehensive sampling vs full-track benchmark."""

    def __init__(self):
        self.results = []
        self.sr = 44100

    def run_comparison(self, track_path: Path, sampling_configs: List[Tuple[float, float]]):
        """
        Run comprehensive comparison for a single track.

        Args:
            track_path: Path to audio file
            sampling_configs: List of (chunk_duration, interval_duration) tuples
        """
        print(f"\n{'='*80}")
        print(f"Track: {track_path.stem}")
        print(f"{'='*80}")

        # Get full-track baseline
        full_result = benchmark_track_fulltrack(track_path, self.sr)

        if full_result["error"]:
            print(f"❌ Full-track analysis failed: {full_result['error']}")
            return

        duration_s = full_result["duration_s"]
        time_full = full_result["time_full"]
        features_full = full_result["features_full"]

        print(f"Duration: {duration_s:.1f}s | Full-track time: {time_full:.3f}s")
        print(f"Full-track features: {features_full}")

        # Baseline throughput
        throughput_full = duration_s / time_full if time_full > 0 else 0
        print(f"Full-track throughput: {throughput_full:.1f}x realtime\n")

        # Try each sampling configuration
        print(f"{'Strategy':<35} {'Time':<10} {'Speedup':<10} {'Corr':<8} {'MAE':<8}")
        print("-" * 80)

        for chunk_dur, interval_dur in sampling_configs:
            sampled_result = benchmark_track_sampled(
                track_path,
                self.sr,
                chunk_duration=chunk_dur,
                interval_duration=interval_dur
            )

            if sampled_result["error"]:
                print(f"❌ Sampling ({chunk_dur}s/{interval_dur}s) failed: {sampled_result['error']}")
                continue

            time_sampled = sampled_result["time_sampled"]
            features_sampled = sampled_result["features_sampled"]

            # Calculate metrics
            speedup = time_full / time_sampled if time_sampled > 0 else 0
            correlation = calculate_feature_correlation(features_full, features_sampled)
            mae = calculate_feature_mae(features_full, features_sampled)

            strategy_name = f"{chunk_dur:.0f}s chunks / {interval_dur:.0f}s interval"

            print(
                f"{strategy_name:<35} {time_sampled:>8.3f}s {speedup:>8.2f}x "
                f"{correlation:>7.3f} {mae:>7.4f}"
            )

            self.results.append({
                "track": track_path.stem,
                "duration_s": duration_s,
                "strategy": strategy_name,
                "chunk_duration": chunk_dur,
                "interval_duration": interval_dur,
                "time_full": time_full,
                "time_sampled": time_sampled,
                "speedup": speedup,
                "correlation": correlation,
                "mae": mae,
                "features_full": features_full,
                "features_sampled": features_sampled,
            })

    def print_summary(self):
        """Print overall summary."""
        if not self.results:
            print("No results to summarize")
            return

        print(f"\n{'='*100}")
        print("SAMPLING STRATEGY SUMMARY (Aggregated across all tracks)")
        print(f"{'='*100}\n")

        # Group by strategy
        strategies = {}
        for result in self.results:
            strategy = result["strategy"]
            if strategy not in strategies:
                strategies[strategy] = []
            strategies[strategy].append(result)

        # Print summary for each strategy
        print(f"{'Strategy':<35} {'Avg Speedup':<15} {'Avg Corr':<12} {'Avg MAE':<10} {'Tracks':<8}")
        print("-" * 100)

        for strategy in sorted(strategies.keys()):
            results_for_strategy = strategies[strategy]
            avg_speedup = np.mean([r["speedup"] for r in results_for_strategy])
            avg_corr = np.mean([r["correlation"] for r in results_for_strategy])
            avg_mae = np.mean([r["mae"] for r in results_for_strategy])
            n_tracks = len(results_for_strategy)

            print(
                f"{strategy:<35} {avg_speedup:>13.2f}x {avg_corr:>10.3f} "
                f"{avg_mae:>8.4f} {n_tracks:>7}"
            )

        # Print best strategy
        print(f"\n{'='*100}")
        best_idx = np.argmax([np.mean([r["speedup"] for r in strategies[s]]) for s in strategies])
        best_strategy = sorted(strategies.keys())[best_idx]
        best_results = strategies[best_strategy]
        best_speedup = np.mean([r["speedup"] for r in best_results])
        best_corr = np.mean([r["correlation"] for r in best_results])

        print(f"✅ Recommended Strategy: {best_strategy}")
        print(f"   Average speedup: {best_speedup:.2f}x")
        print(f"   Feature correlation: {best_corr:.3f}")
        print(f"{'='*100}\n")

    def run(self):
        """Run full benchmark suite."""
        album_path = Path("/mnt/Musica/Musica/Pearl Jam/1991 - Ten")
        tracks = sorted([f for f in album_path.glob("*.flac")])[:5]  # First 5 tracks for quick testing

        print("\n╔" + "═" * 98 + "╗")
        print("║" + " " * 24 + "SAMPLING STRATEGY EVALUATION" + " " * 47 + "║")
        print("╚" + "═" * 98 + "╝")

        print(f"\nAlbum: {album_path}")
        print(f"Test Tracks: {len(tracks)}")

        # Test different sampling configurations
        sampling_configs = [
            (5.0, 10.0),   # 5s chunks every 10s (50% coverage)
            (5.0, 15.0),   # 5s chunks every 15s (33% coverage)
            (5.0, 20.0),   # 5s chunks every 20s (25% coverage)
        ]

        for track_path in tracks:
            self.run_comparison(track_path, sampling_configs)

        self.print_summary()


def main():
    """Run sampling benchmark."""
    bench = SamplingBenchmark()
    bench.run()


if __name__ == "__main__":
    main()

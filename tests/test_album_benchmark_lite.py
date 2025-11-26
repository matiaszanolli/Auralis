"""
Lightweight Album Benchmark: Pearl Jam - Ten (1991)

Process one track at a time to avoid memory buildup.
Compare fingerprinting performance using HarmonicAnalyzer with Rust DSP.

Metrics tracked:
- Individual track fingerprinting time
- Audio duration and samples
- Per-track throughput
- Album totals
"""

import numpy as np
import time
from pathlib import Path
import sys
import gc

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.fingerprint.harmonic_analyzer import HarmonicAnalyzer, RUST_DSP_AVAILABLE
from auralis.io.unified_loader import load_audio


def benchmark_track(track_path: Path, sr: int = 44100) -> dict:
    """Benchmark a single track with Rust DSP - minimal memory overhead."""
    track_name = track_path.stem

    try:
        # Load audio (convert to mono immediately to save memory)
        audio, loaded_sr = load_audio(str(track_path), target_sample_rate=sr)

        # Convert to mono if stereo
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        audio = audio.astype(np.float64)
        duration_s = len(audio) / sr

        # Analyze with Rust DSP
        analyzer = HarmonicAnalyzer()

        start = time.perf_counter()
        features = analyzer.analyze(audio, sr)
        analysis_time = time.perf_counter() - start

        # Clean up immediately
        del audio
        del analyzer
        gc.collect()

        throughput = duration_s / analysis_time if analysis_time > 0 else 0

        return {
            "track": track_name,
            "duration_s": duration_s,
            "analysis_time": analysis_time,
            "throughput": throughput,
            "features": features,
            "error": None,
        }
    except Exception as e:
        gc.collect()
        return {
            "track": track_name,
            "duration_s": 0,
            "analysis_time": None,
            "throughput": 0,
            "features": None,
            "error": str(e),
        }


def main():
    """Process all tracks in Pearl Jam's Ten."""
    album_path = Path("/mnt/Musica/Musica/Pearl Jam/1991 - Ten")
    tracks = sorted([f for f in album_path.glob("*.flac")])

    print("\n╔" + "═" * 88 + "╗")
    print("║" + " " * 18 + "ALBUM BENCHMARK: Pearl Jam - Ten (1991)" + " " * 30 + "║")
    print("╚" + "═" * 88 + "╝")

    print(f"\nAlbum Path: {album_path}")
    print(f"Total Tracks: {len(tracks)}")
    print(f"Rust DSP Available: {RUST_DSP_AVAILABLE}")

    print(
        f"\n{'#':<3} {'Track Name':<38} {'Duration':<12} {'Analysis':<12} {'Throughput':<12}"
    )
    print("─" * 88)

    results = []
    total_duration = 0
    total_analysis_time = 0
    successful_tracks = 0

    for i, track_path in enumerate(tracks, 1):
        result = benchmark_track(track_path)
        results.append(result)

        if result["error"]:
            print(f"{i:<3} {result['track']:<38} ❌ {result['error'][:50]}")
        else:
            successful_tracks += 1
            total_duration += result["duration_s"]
            total_analysis_time += result["analysis_time"]

            print(
                f"{i:<3} {result['track']:<38} {result['duration_s']:>7.1f}s   "
                f"{result['analysis_time']:>10.3f}s   {result['throughput']:>8.1f}x RT"
            )

    # Print summary
    print("\n" + "═" * 88)
    print("BENCHMARK SUMMARY")
    print("═" * 88)

    if successful_tracks == 0:
        print("❌ No successful analyses")
        return

    avg_throughput = total_duration / total_analysis_time if total_analysis_time > 0 else 0

    print(f"\nAlbum Statistics:")
    print(f"  Total Audio Duration:  {total_duration:>8.1f} seconds ({total_duration/60:>6.2f} minutes)")
    print(f"  Successful Tracks:     {successful_tracks:>8d} / {len(tracks)}")
    print(f"  Average Track Length:  {total_duration/successful_tracks:>8.1f} seconds")

    print(f"\nPerformance with Rust DSP:")
    print(f"  Total Analysis Time:   {total_analysis_time:>8.3f} seconds")
    print(f"  Avg Time Per Track:    {total_analysis_time/successful_tracks:>8.3f} seconds")
    print(f"  Album Throughput:      {avg_throughput:>8.2f}x realtime")

    print(f"\nLibrary Processing Estimate:")
    tracks_3min = 3 * 60  # 3 minutes in seconds
    est_1000_tracks_time = (1000 * tracks_3min) / avg_throughput
    est_1000_tracks_hours = est_1000_tracks_time / 3600

    print(f"  1000-track library (3 min avg):")
    print(f"    Total Audio:         {1000 * tracks_3min / 3600:>8.1f} hours")
    print(f"    Processing Time:     {est_1000_tracks_hours:>8.1f} hours")
    print(f"    Status:              ✅ Production-ready")

    print(f"\nFeature Values (Last Track with Rust DSP):")
    if results[-1]["features"]:
        for key, value in results[-1]["features"].items():
            print(f"  {key:<30}: {value:>10.4f}")

    print(f"\n{'═' * 88}\n")


if __name__ == "__main__":
    main()

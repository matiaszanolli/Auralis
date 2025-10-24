#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EQ Processing Performance Benchmark
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Focused benchmark for parallel EQ processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import time
from typing import Dict, List

# Auralis imports
from auralis.dsp.eq.filters import apply_eq_gains
from auralis.dsp.eq.parallel_eq_processor import (
    ParallelEQProcessor,
    VectorizedEQProcessor,
    ParallelEQConfig,
    create_optimal_eq_processor
)
from auralis.dsp.eq.critical_bands import create_critical_bands, create_frequency_mapping


def generate_test_audio(duration_sec: float, sample_rate: int = 44100) -> np.ndarray:
    """Generate test audio with multiple frequencies"""
    num_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, num_samples)

    # Multi-frequency content
    audio = np.zeros(num_samples)
    frequencies = [100, 250, 500, 1000, 2000, 4000, 8000, 12000]
    for freq in frequencies:
        audio += 0.1 * np.sin(2 * np.pi * freq * t)

    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.8

    return audio


def benchmark_eq_method(
    func,
    audio: np.ndarray,
    gains: np.ndarray,
    freq_to_band_map: np.ndarray,
    fft_size: int,
    method_name: str,
    num_runs: int = 5
) -> Dict:
    """Benchmark a single EQ method"""
    print(f"  Testing {method_name}...", end=" ", flush=True)

    # Warm-up
    try:
        _ = func(audio, gains, freq_to_band_map, fft_size)
    except Exception as e:
        print(f"FAILED: {e}")
        return None

    # Timed runs
    durations = []
    for _ in range(num_runs):
        start = time.perf_counter()
        result = func(audio, gains, freq_to_band_map, fft_size)
        end = time.perf_counter()
        durations.append((end - start) * 1000)  # ms

    avg_duration = np.mean(durations)
    std_duration = np.std(durations)

    # Calculate real-time factor
    audio_duration = len(audio) / 44100
    realtime_factor = audio_duration / (avg_duration / 1000)

    print(f"{avg_duration:.3f}ms ± {std_duration:.3f}ms ({realtime_factor:.1f}x RT)")

    return {
        'method': method_name,
        'avg_ms': avg_duration,
        'std_ms': std_duration,
        'realtime_factor': realtime_factor,
        'result': result
    }


def test_eq_accuracy(results: Dict[str, Dict]):
    """Test that all methods produce similar results"""
    print("\n[Accuracy Validation]")

    if not results or len(results) < 2:
        print("  Not enough results to compare")
        return

    # Get reference result (sequential)
    ref_key = 'Sequential (Original)'
    if ref_key not in results or results[ref_key] is None:
        print("  No reference result available")
        return

    ref_audio = results[ref_key]['result']

    # Compare all other methods to reference
    for method_name, result_data in results.items():
        if method_name == ref_key or result_data is None:
            continue

        test_audio = result_data['result']

        # Calculate difference metrics
        mse = np.mean((ref_audio - test_audio) ** 2)
        max_diff = np.max(np.abs(ref_audio - test_audio))
        correlation = np.corrcoef(ref_audio.flatten(), test_audio.flatten())[0, 1]

        print(f"  {method_name:30s}: MSE={mse:.2e}, MaxDiff={max_diff:.2e}, Corr={correlation:.6f}")

        if correlation > 0.9999:
            print(f"    ✅ Excellent accuracy")
        elif correlation > 0.999:
            print(f"    ⚠️  Good accuracy (minor differences)")
        else:
            print(f"    ❌ Poor accuracy (significant differences)")


def main():
    print("=" * 70)
    print("EQ Processing Performance Benchmark")
    print("=" * 70)

    # Setup
    sample_rate = 44100
    fft_size = 4096
    num_runs = 5

    # Create critical bands and frequency mapping
    critical_bands = create_critical_bands()
    freq_to_band_map = create_frequency_mapping(critical_bands, sample_rate, fft_size)
    num_bands = len(critical_bands)

    print(f"\nConfiguration:")
    print(f"  Sample rate: {sample_rate} Hz")
    print(f"  FFT size: {fft_size}")
    print(f"  Number of bands: {num_bands}")
    print(f"  Runs per test: {num_runs}")

    # Create test gains (boost mid-range, cut lows/highs)
    gains = np.zeros(num_bands)
    for i in range(num_bands):
        center_freq = critical_bands[i].center_freq
        if 500 <= center_freq <= 2000:
            gains[i] = 3.0  # +3 dB boost
        elif center_freq < 100 or center_freq > 10000:
            gains[i] = -2.0  # -2 dB cut

    # Test configurations
    test_configs = [
        ("Short (5s)", 5),
        ("Medium (30s)", 30),
        ("Long (180s)", 180)
    ]

    all_results = {}

    for config_name, duration in test_configs:
        print(f"\n{'=' * 70}")
        print(f"Test: {config_name}")
        print(f"{'=' * 70}")

        # Generate audio
        audio = generate_test_audio(duration, sample_rate)
        print(f"Generated {duration}s audio: {len(audio)} samples ({audio.nbytes / 1024:.1f} KB)")

        results = {}

        # 1. Sequential (Original)
        print("\n[Sequential Processing]")
        result = benchmark_eq_method(
            apply_eq_gains,
            audio,
            gains,
            freq_to_band_map,
            fft_size,
            "Sequential (Original)",
            num_runs
        )
        if result:
            results['Sequential (Original)'] = result

        # 2. Vectorized
        print("\n[Vectorized Processing]")
        vec_processor = VectorizedEQProcessor()
        result = benchmark_eq_method(
            vec_processor.apply_eq_gains_vectorized,
            audio,
            gains,
            freq_to_band_map,
            fft_size,
            "Vectorized",
            num_runs
        )
        if result:
            results['Vectorized'] = result

        # 3. Parallel (No Grouping)
        print("\n[Parallel Processing - Individual Bands]")
        parallel_config = ParallelEQConfig(
            enable_parallel=True,
            max_workers=8,
            use_band_grouping=False,
            min_bands_for_parallel=4
        )
        parallel_processor = ParallelEQProcessor(parallel_config)
        result = benchmark_eq_method(
            parallel_processor.apply_eq_gains_parallel,
            audio,
            gains,
            freq_to_band_map,
            fft_size,
            "Parallel (8 workers, no grouping)",
            num_runs
        )
        if result:
            results['Parallel (No Grouping)'] = result

        # 4. Parallel (With Grouping)
        print("\n[Parallel Processing - Band Grouping]")
        grouped_config = ParallelEQConfig(
            enable_parallel=True,
            max_workers=8,
            use_band_grouping=True,
            min_bands_for_parallel=4
        )
        grouped_processor = ParallelEQProcessor(grouped_config)
        result = benchmark_eq_method(
            grouped_processor.apply_eq_gains_parallel,
            audio,
            gains,
            freq_to_band_map,
            fft_size,
            "Parallel (8 workers, band grouping)",
            num_runs
        )
        if result:
            results['Parallel (With Grouping)'] = result

        # 5. Parallel (4 workers)
        print("\n[Parallel Processing - 4 Workers]")
        parallel_4_config = ParallelEQConfig(
            enable_parallel=True,
            max_workers=4,
            use_band_grouping=True,
            min_bands_for_parallel=4
        )
        parallel_4_processor = ParallelEQProcessor(parallel_4_config)
        result = benchmark_eq_method(
            parallel_4_processor.apply_eq_gains_parallel,
            audio,
            gains,
            freq_to_band_map,
            fft_size,
            "Parallel (4 workers, band grouping)",
            num_runs
        )
        if result:
            results['Parallel (4 workers)'] = result

        # Accuracy validation
        test_eq_accuracy(results)

        # Speedup analysis
        print(f"\n{'=' * 70}")
        print(f"Speedup Analysis ({config_name})")
        print(f"{'=' * 70}")

        if 'Sequential (Original)' in results:
            seq_time = results['Sequential (Original)']['avg_ms']

            for method_name, result_data in results.items():
                if method_name == 'Sequential (Original)':
                    continue

                method_time = result_data['avg_ms']
                speedup = seq_time / method_time

                if speedup > 1:
                    print(f"  {method_name:40s}: {speedup:.2f}x FASTER ({seq_time:.2f}ms → {method_time:.2f}ms)")
                elif speedup < 1:
                    print(f"  {method_name:40s}: {1/speedup:.2f}x SLOWER ({seq_time:.2f}ms → {method_time:.2f}ms)")
                else:
                    print(f"  {method_name:40s}: Same speed ({seq_time:.2f}ms)")

        all_results[config_name] = results

    # Overall summary
    print(f"\n{'=' * 70}")
    print("OVERALL SUMMARY")
    print(f"{'=' * 70}")

    # Find best method for each duration
    for config_name, results in all_results.items():
        if not results:
            continue

        print(f"\n{config_name}:")

        # Sort by speed
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1]['avg_ms']
        )

        print(f"  Fastest: {sorted_results[0][0]} ({sorted_results[0][1]['avg_ms']:.2f}ms)")

        if len(sorted_results) > 1:
            fastest_time = sorted_results[0][1]['avg_ms']
            seq_result = results.get('Sequential (Original)')
            if seq_result:
                seq_time = seq_result['avg_ms']
                overall_speedup = seq_time / fastest_time
                print(f"  Best speedup vs sequential: {overall_speedup:.2f}x")

    print(f"\n{'=' * 70}")
    print("Recommendations:")
    print(f"{'=' * 70}")
    print("  • Vectorized: Best for short audio (< 10s)")
    print("  • Parallel with grouping: Best for medium/long audio (> 10s)")
    print("  • Use 4-8 workers for optimal performance")
    print("  • Band grouping reduces thread overhead significantly")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Vectorization Performance Benchmark
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Benchmark vectorized vs original implementations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import time
from typing import Dict

# Original implementation
from auralis.dsp.dynamics.envelope import EnvelopeFollower

# Vectorized implementations
try:
    from auralis.dsp.dynamics.vectorized_envelope import (
        VectorizedEnvelopeFollower,
        FastEnvelopeFollower
    )
    VECTORIZED_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import vectorized envelope: {e}")
    VECTORIZED_AVAILABLE = False


def benchmark_envelope_follower():
    """Benchmark envelope follower implementations"""
    print("=" * 70)
    print("Envelope Follower Vectorization Benchmark")
    print("=" * 70)

    sample_rate = 44100
    attack_ms = 10.0
    release_ms = 100.0
    num_runs = 10

    # Test configurations
    test_configs = [
        ("Short buffer (1024 samples)", 1024),
        ("Medium buffer (44100 samples, 1s)", 44100),
        ("Long buffer (441000 samples, 10s)", 441000),
        ("Very long buffer (4410000 samples, 100s)", 4410000)
    ]

    for config_name, buffer_size in test_configs:
        print(f"\n{'=' * 70}")
        print(f"Test: {config_name}")
        print(f"{'=' * 70}")

        # Generate test data (varying levels)
        t = np.linspace(0, buffer_size / sample_rate, buffer_size)
        input_levels = np.abs(0.5 * np.sin(2 * np.pi * 10 * t) + 0.3 * np.random.randn(buffer_size) * 0.1)
        input_levels = np.clip(input_levels, 0, 1)

        print(f"Buffer size: {buffer_size} samples ({buffer_size/sample_rate:.2f}s)")
        print(f"Data size: {input_levels.nbytes / 1024:.1f} KB")

        results = {}

        # 1. Original (sample-by-sample loop)
        print("\n[Original Implementation]")
        original_follower = EnvelopeFollower(sample_rate, attack_ms, release_ms)

        durations = []
        for _ in range(num_runs):
            original_follower.reset()
            start = time.perf_counter()
            result_original = original_follower.process_buffer(input_levels)
            end = time.perf_counter()
            durations.append((end - start) * 1000)

        avg_original = np.mean(durations)
        std_original = np.std(durations)
        print(f"  Duration: {avg_original:.3f}ms ± {std_original:.3f}ms")

        results['original'] = {
            'duration_ms': avg_original,
            'result': result_original
        }

        if not VECTORIZED_AVAILABLE:
            print("\n⚠️  Vectorized implementations not available")
            continue

        # 2. Vectorized (NumPy, no Numba)
        print("\n[Vectorized (Pure NumPy)]")
        vectorized_follower = VectorizedEnvelopeFollower(sample_rate, attack_ms, release_ms, use_numba=False)

        durations = []
        for _ in range(num_runs):
            vectorized_follower.reset()
            start = time.perf_counter()
            result_vectorized = vectorized_follower.process_buffer(input_levels)
            end = time.perf_counter()
            durations.append((end - start) * 1000)

        avg_vectorized = np.mean(durations)
        std_vectorized = np.std(durations)
        speedup_vectorized = avg_original / avg_vectorized
        print(f"  Duration: {avg_vectorized:.3f}ms ± {std_vectorized:.3f}ms")
        print(f"  Speedup: {speedup_vectorized:.2f}x")

        results['vectorized'] = {
            'duration_ms': avg_vectorized,
            'speedup': speedup_vectorized,
            'result': result_vectorized
        }

        # 3. Vectorized with Numba
        print("\n[Vectorized (Numba JIT)]")
        numba_follower = VectorizedEnvelopeFollower(sample_rate, attack_ms, release_ms, use_numba=True)

        try:
            # Warm-up run for JIT compilation
            numba_follower.reset()
            _ = numba_follower.process_buffer(input_levels[:100])

            durations = []
            for _ in range(num_runs):
                numba_follower.reset()
                start = time.perf_counter()
                result_numba = numba_follower.process_buffer(input_levels)
                end = time.perf_counter()
                durations.append((end - start) * 1000)

            avg_numba = np.mean(durations)
            std_numba = np.std(durations)
            speedup_numba = avg_original / avg_numba
            print(f"  Duration: {avg_numba:.3f}ms ± {std_numba:.3f}ms")
            print(f"  Speedup: {speedup_numba:.2f}x")

            results['numba'] = {
                'duration_ms': avg_numba,
                'speedup': speedup_numba,
                'result': result_numba
            }
        except Exception as e:
            print(f"  ⚠️  Numba not available: {e}")

        # 4. Fast (chunked processing)
        print("\n[Fast (Chunked Processing)]")
        fast_follower = FastEnvelopeFollower(sample_rate, attack_ms, release_ms)

        durations = []
        for _ in range(num_runs):
            fast_follower.envelope = 0.0
            start = time.perf_counter()
            result_fast = fast_follower.process_buffer_fast(input_levels)
            end = time.perf_counter()
            durations.append((end - start) * 1000)

        avg_fast = np.mean(durations)
        std_fast = np.std(durations)
        speedup_fast = avg_original / avg_fast
        print(f"  Duration: {avg_fast:.3f}ms ± {std_fast:.3f}ms")
        print(f"  Speedup: {speedup_fast:.2f}x")

        results['fast'] = {
            'duration_ms': avg_fast,
            'speedup': speedup_fast,
            'result': result_fast
        }

        # Accuracy comparison
        print(f"\n{'=' * 70}")
        print("Accuracy Validation")
        print(f"{'=' * 70}")

        ref_result = results['original']['result']

        for method_name, result_data in results.items():
            if method_name == 'original':
                continue

            test_result = result_data['result']

            # Calculate metrics
            mse = np.mean((ref_result - test_result) ** 2)
            max_diff = np.max(np.abs(ref_result - test_result))
            correlation = np.corrcoef(ref_result, test_result)[0, 1]

            print(f"\n{method_name.upper()}:")
            print(f"  MSE: {mse:.2e}")
            print(f"  Max Diff: {max_diff:.2e}")
            print(f"  Correlation: {correlation:.8f}")

            if correlation > 0.9999:
                print(f"  ✅ Excellent accuracy")
            elif correlation > 0.999:
                print(f"  ⚠️  Good accuracy")
            else:
                print(f"  ❌ Poor accuracy")

        # Summary for this config
        print(f"\n{'=' * 70}")
        print(f"Summary ({config_name})")
        print(f"{'=' * 70}")

        best_method = min(results.items(), key=lambda x: x[1]['duration_ms'])
        print(f"Fastest method: {best_method[0].upper()}")
        print(f"Best speedup: {results[best_method[0]].get('speedup', 1.0):.2f}x")

    # Overall recommendations
    print(f"\n{'=' * 70}")
    print("RECOMMENDATIONS")
    print(f"{'=' * 70}")
    print("  • For short buffers (<1s): Use original (overhead dominates)")
    print("  • For medium buffers (1-10s): Use vectorized or Numba")
    print("  • For long buffers (>10s): Use Numba JIT (10-20x speedup)")
    print("  • If Numba unavailable: Use pure NumPy vectorized")
    print("  • Chunked processing: Good for cache locality")


if __name__ == "__main__":
    if not VECTORIZED_AVAILABLE:
        print("ERROR: Vectorized envelope implementations not available")
        print("Make sure vectorized_envelope.py is in auralis/dsp/dynamics/")
        exit(1)

    benchmark_envelope_follower()

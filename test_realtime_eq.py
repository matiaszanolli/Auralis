#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Real-time Adaptive EQ Test
~~~~~~~~~~~~~~~~~~~~~~~~~~

Test the real-time adaptive EQ with critical bands
"""

import numpy as np
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

from auralis.core.unified_config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.dsp.realtime_adaptive_eq import create_realtime_adaptive_eq


def create_test_stream():
    """Create a test audio stream with varying characteristics"""

    sample_rate = 44100
    chunk_size = 512  # Small chunks for real-time simulation
    duration = 10.0   # 10 seconds total

    total_samples = int(sample_rate * duration)
    num_chunks = total_samples // chunk_size

    chunks = []
    t_offset = 0

    for i in range(num_chunks):
        t = np.linspace(t_offset, t_offset + chunk_size/sample_rate, chunk_size)

        # Create varying audio characteristics
        if i < num_chunks // 3:
            # Classical-like: lower frequencies, dynamic
            chunk = (
                0.3 * np.sin(2 * np.pi * 220 * t) +  # A3
                0.2 * np.sin(2 * np.pi * 330 * t) +  # E4
                0.1 * np.sin(2 * np.pi * 440 * t)    # A4
            ) * (0.3 + 0.7 * np.sin(2 * np.pi * 0.5 * (t_offset + t)))
        elif i < 2 * num_chunks // 3:
            # Electronic-like: high frequencies, steady
            chunk = (
                0.4 * np.sin(2 * np.pi * 880 * t) +  # High freq
                0.3 * np.sin(2 * np.pi * 1760 * t) + # Even higher
                0.2 * np.sin(2 * np.pi * 110 * t)    # Sub bass
            ) * 0.8
        else:
            # Rock-like: midrange heavy
            chunk = (
                0.5 * np.sin(2 * np.pi * 165 * t) +  # Power chord
                0.4 * np.sin(2 * np.pi * 247 * t) +  # Harmonics
                0.3 * np.random.randn(chunk_size) * 0.2  # Distortion
            ) * 0.9

        chunks.append(chunk)
        t_offset += chunk_size / sample_rate

    return chunks


def test_realtime_adaptive_eq():
    """Test the real-time adaptive EQ system"""

    print("=" * 60)
    print("Real-time Adaptive EQ Test")
    print("=" * 60)

    # Create configuration
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")

    # Initialize processor
    print("Initializing Hybrid Processor...")
    processor = HybridProcessor(config)

    # Get initial EQ info
    eq_info = processor.get_realtime_eq_info()
    print(f"Buffer size: {eq_info['buffer_size']} samples")
    print(f"Target latency: {eq_info['target_latency_ms']:.1f} ms")

    # Create test stream
    print("\nCreating test audio stream...")
    audio_chunks = create_test_stream()

    print(f"Created {len(audio_chunks)} chunks of {len(audio_chunks[0])} samples each")

    # Process stream
    print("\nProcessing real-time stream...")
    print("-" * 40)

    processed_chunks = []
    processing_times = []
    eq_curves = []

    for i, chunk in enumerate(audio_chunks):
        start_time = time.time()

        # Process chunk in real-time
        processed_chunk = processor.process_realtime_chunk(chunk)
        processed_chunks.append(processed_chunk)

        processing_time = (time.time() - start_time) * 1000
        processing_times.append(processing_time)

        # Sample EQ curve every 20 chunks
        if i % 20 == 0:
            eq_info = processor.get_realtime_eq_info()
            eq_curves.append(eq_info['eq_curve'])

            print(f"Chunk {i:3d}: {processing_time:.2f}ms, "
                  f"Latency: {eq_info['actual_latency_ms']:.1f}ms")

    # Analyze results
    print("\n" + "=" * 60)
    print("Performance Analysis")
    print("=" * 60)

    avg_processing_time = np.mean(processing_times)
    max_processing_time = np.max(processing_times)
    min_processing_time = np.min(processing_times)

    print(f"Processing time (ms):")
    print(f"  Average: {avg_processing_time:.2f}")
    print(f"  Maximum: {max_processing_time:.2f}")
    print(f"  Minimum: {min_processing_time:.2f}")

    # Check real-time performance
    chunk_duration_ms = len(audio_chunks[0]) / config.internal_sample_rate * 1000
    print(f"Chunk duration: {chunk_duration_ms:.2f} ms")

    if avg_processing_time < chunk_duration_ms:
        print("✓ Real-time performance achieved!")
    else:
        print("✗ Processing too slow for real-time")

    # Analyze EQ adaptation
    print(f"\nEQ Adaptation Analysis:")
    print(f"Captured {len(eq_curves)} EQ snapshots")

    if len(eq_curves) >= 2:
        print(f"EQ curve structure: {list(eq_curves[0].keys())}")

        # Check for the correct key structure
        if 'critical_band_gains' in eq_curves[0]:
            first_curve = eq_curves[0]['critical_band_gains']
            last_curve = eq_curves[-1]['critical_band_gains']

            curve_change = np.mean(np.abs(np.array(last_curve) - np.array(first_curve)))
            print(f"Average EQ change: {curve_change:.3f} dB")

            if curve_change > 0.1:
                print("✓ EQ is adapting to content changes")
            else:
                print("→ EQ adaptation is stable/minimal")
        else:
            print("→ EQ curve data structure not as expected")
            curve_change = 0

    # Final performance stats
    final_eq_info = processor.get_realtime_eq_info()
    final_performance = final_eq_info['performance']

    print(f"\nFinal Performance Stats:")
    print(f"  Adaptation updates: {final_performance.get('adaptation_updates', 0)}")
    print(f"  Buffer underruns: {final_performance.get('buffer_underruns', 0)}")

    return {
        'avg_processing_time_ms': avg_processing_time,
        'max_processing_time_ms': max_processing_time,
        'real_time_capable': avg_processing_time < chunk_duration_ms,
        'eq_adaptation_active': curve_change > 0.1 if len(eq_curves) >= 2 else False,
        'total_chunks_processed': len(audio_chunks)
    }


def test_eq_parameter_adjustment():
    """Test dynamic EQ parameter adjustment"""

    print("\n" + "=" * 60)
    print("Dynamic Parameter Adjustment Test")
    print("=" * 60)

    # Create configuration
    config = UnifiedConfig()
    processor = HybridProcessor(config)

    # Create test chunk
    test_chunk = np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, 4410)) * 0.5

    # Test different adaptation rates
    adaptation_rates = [0.05, 0.1, 0.2, 0.5]

    print("Testing adaptation rate changes:")
    for rate in adaptation_rates:
        processor.set_realtime_eq_parameters(adaptation_rate=rate)

        # Process a few chunks
        for _ in range(5):
            processor.process_realtime_chunk(test_chunk)

        eq_info = processor.get_realtime_eq_info()
        actual_rate = eq_info['adaptation_rate']
        print(f"  Set rate: {rate:.2f}, Actual: {actual_rate:.2f}")

    # Test gain limits
    print("\nTesting gain limit changes:")
    gain_limits = [6.0, 12.0, 18.0]

    for limit in gain_limits:
        processor.set_realtime_eq_parameters(max_gain_db=limit)
        print(f"  Max gain set to: {limit:.1f} dB")

    print("✓ Parameter adjustment test completed")


if __name__ == "__main__":
    try:
        # Run real-time EQ test
        results = test_realtime_adaptive_eq()

        # Run parameter adjustment test
        test_eq_parameter_adjustment()

        print("\n" + "=" * 60)
        print("Real-time Adaptive EQ Test Results:")
        print("=" * 60)
        print(f"Real-time capable: {results['real_time_capable']}")
        print(f"EQ adaptation active: {results['eq_adaptation_active']}")
        print(f"Average processing time: {results['avg_processing_time_ms']:.2f} ms")
        print(f"Total chunks processed: {results['total_chunks_processed']}")

        if results['real_time_capable'] and results['eq_adaptation_active']:
            print("\n✓ Real-time Adaptive EQ system is working correctly!")
        else:
            print("\n→ Some aspects may need optimization")

        print("=" * 60)

    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
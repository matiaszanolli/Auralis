#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Performance Benchmark Suite
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive benchmarking for Auralis performance optimizations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import time
from typing import Dict, List, Tuple, Callable
from dataclasses import dataclass, asdict
import json
from pathlib import Path

# Auralis imports
from auralis.analysis.spectrum_analyzer import SpectrumAnalyzer, SpectrumSettings
from auralis.analysis.parallel_spectrum_analyzer import (
    ParallelSpectrumAnalyzer,
    ParallelSpectrumSettings
)
from auralis.core.analysis.content_analyzer import ContentAnalyzer
from auralis.dsp.eq.psychoacoustic_eq import PsychoacousticEQ, EQSettings
from auralis.dsp.advanced_dynamics import DynamicsProcessor, create_dynamics_processor
from auralis.dsp.dynamics import DynamicsMode
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.optimization.parallel_processor import ParallelConfig, get_parallel_processor


@dataclass
class BenchmarkResult:
    """Result from a single benchmark"""
    name: str
    duration_ms: float
    operations_per_second: float
    memory_mb: float
    cpu_usage_percent: float
    parallel: bool
    workers: int
    audio_duration_sec: float
    realtime_factor: float  # How many times faster than real-time


@dataclass
class BenchmarkSummary:
    """Summary of benchmark results"""
    sequential_results: List[BenchmarkResult]
    parallel_results: List[BenchmarkResult]
    speedup_factors: Dict[str, float]
    total_speedup: float
    timestamp: str


class PerformanceBenchmark:
    """Main benchmarking class"""

    def __init__(self, output_dir: str = "benchmark_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Test audio configurations
        self.test_configs = [
            ("short", 5, 44100),      # 5 seconds
            ("medium", 30, 44100),    # 30 seconds
            ("long", 180, 44100),     # 3 minutes
        ]

        # Initialize results storage
        self.results = []

    def generate_test_audio(self, duration_sec: float, sample_rate: int) -> np.ndarray:
        """Generate synthetic test audio with realistic characteristics"""
        num_samples = int(duration_sec * sample_rate)

        # Generate multi-frequency sine wave with harmonics (stereo)
        t = np.linspace(0, duration_sec, num_samples)

        # Fundamental + harmonics
        frequencies = [440, 880, 1320, 1760, 2200]  # A4 and harmonics
        audio_left = np.zeros(num_samples)
        audio_right = np.zeros(num_samples)

        for i, freq in enumerate(frequencies):
            amplitude = 0.2 / (i + 1)  # Decreasing amplitude for harmonics
            audio_left += amplitude * np.sin(2 * np.pi * freq * t)
            audio_right += amplitude * np.sin(2 * np.pi * freq * t + np.pi / 4)  # Phase shift

        # Add some dynamics (envelope)
        envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t)  # 0.5 Hz modulation
        audio_left *= envelope
        audio_right *= envelope

        # Add noise for realism
        noise_level = 0.01
        audio_left += noise_level * np.random.randn(num_samples)
        audio_right += noise_level * np.random.randn(num_samples)

        # Combine to stereo
        audio = np.column_stack([audio_left, audio_right])

        # Normalize
        audio = audio / np.max(np.abs(audio)) * 0.8

        return audio

    def benchmark_function(
        self,
        func: Callable,
        func_name: str,
        audio: np.ndarray,
        parallel: bool = False,
        workers: int = 1,
        **kwargs
    ) -> BenchmarkResult:
        """
        Benchmark a single function

        Args:
            func: Function to benchmark
            func_name: Name for reporting
            audio: Test audio
            parallel: Whether this is parallel version
            workers: Number of workers
            **kwargs: Additional arguments for function

        Returns:
            BenchmarkResult
        """
        print(f"  Benchmarking {func_name} ({'parallel' if parallel else 'sequential'})...", end=" ", flush=True)

        # Warm-up run
        try:
            _ = func(audio, **kwargs)
        except Exception as e:
            print(f"FAILED: {e}")
            return None

        # Timed runs (average of 3)
        durations = []
        for _ in range(3):
            start_time = time.perf_counter()
            result = func(audio, **kwargs)
            end_time = time.perf_counter()
            durations.append((end_time - start_time) * 1000)  # Convert to ms

        avg_duration_ms = np.mean(durations)
        std_duration_ms = np.std(durations)

        # Calculate metrics
        audio_duration_sec = len(audio) / 44100
        ops_per_second = 1000 / avg_duration_ms if avg_duration_ms > 0 else 0
        realtime_factor = audio_duration_sec / (avg_duration_ms / 1000) if avg_duration_ms > 0 else 0

        # Memory usage (rough estimate)
        memory_mb = audio.nbytes / (1024 * 1024)

        print(f"{avg_duration_ms:.2f}ms ± {std_duration_ms:.2f}ms ({realtime_factor:.1f}x real-time)")

        return BenchmarkResult(
            name=func_name,
            duration_ms=avg_duration_ms,
            operations_per_second=ops_per_second,
            memory_mb=memory_mb,
            cpu_usage_percent=0.0,  # Would need psutil for accurate measurement
            parallel=parallel,
            workers=workers,
            audio_duration_sec=audio_duration_sec,
            realtime_factor=realtime_factor
        )

    def benchmark_spectrum_analysis(self, audio: np.ndarray):
        """Benchmark spectrum analysis (sequential vs parallel)"""
        print("\n[Spectrum Analysis]")

        # Sequential
        settings_seq = SpectrumSettings(fft_size=4096, overlap=0.75)
        analyzer_seq = SpectrumAnalyzer(settings_seq)

        result_seq = self.benchmark_function(
            func=lambda a: analyzer_seq.analyze_file(a, sample_rate=44100),
            func_name="spectrum_analysis",
            audio=audio[:, 0],  # Mono for analysis
            parallel=False,
            workers=1
        )

        # Parallel
        settings_par = ParallelSpectrumSettings(
            fft_size=4096,
            overlap=0.75,
            enable_parallel=True,
            max_workers=8
        )
        analyzer_par = ParallelSpectrumAnalyzer(settings_par)

        result_par = self.benchmark_function(
            func=lambda a: analyzer_par.analyze_file(a, sample_rate=44100),
            func_name="spectrum_analysis",
            audio=audio[:, 0],
            parallel=True,
            workers=8
        )

        return result_seq, result_par

    def benchmark_content_analysis(self, audio: np.ndarray):
        """Benchmark content analysis"""
        print("\n[Content Analysis]")

        analyzer = ContentAnalyzer(sample_rate=44100)

        result = self.benchmark_function(
            func=lambda a: analyzer.analyze_content(a),
            func_name="content_analysis",
            audio=audio,
            parallel=False,  # TODO: Add parallel version
            workers=1
        )

        return result, None

    def benchmark_eq_processing(self, audio: np.ndarray):
        """Benchmark EQ processing"""
        print("\n[Psychoacoustic EQ]")

        settings = EQSettings(sample_rate=44100, fft_size=4096)
        eq = PsychoacousticEQ(settings)

        # Create target curve
        target_curve = np.zeros(len(eq.critical_bands))

        # Sequential processing (process in chunks)
        def process_eq_sequential(audio_data):
            chunk_size = 4096
            processed = np.zeros_like(audio_data)
            for i in range(0, len(audio_data) - chunk_size, chunk_size // 2):
                chunk = audio_data[i:i + chunk_size]
                if len(chunk) == chunk_size:
                    processed_chunk = eq.process_realtime_chunk(chunk, target_curve)
                    processed[i:i + chunk_size] = processed_chunk
            return processed

        result = self.benchmark_function(
            func=process_eq_sequential,
            func_name="psychoacoustic_eq",
            audio=audio,
            parallel=False,  # TODO: Add parallel version
            workers=1
        )

        return result, None

    def benchmark_dynamics_processing(self, audio: np.ndarray):
        """Benchmark dynamics processing"""
        print("\n[Dynamics Processing]")

        processor = create_dynamics_processor(
            mode=DynamicsMode.ADAPTIVE,
            sample_rate=44100
        )

        result = self.benchmark_function(
            func=lambda a: processor.process(a, None)[0],
            func_name="dynamics_processing",
            audio=audio,
            parallel=False,  # TODO: Add parallel version
            workers=1
        )

        return result, None

    def benchmark_full_pipeline(self, audio: np.ndarray):
        """Benchmark complete processing pipeline"""
        print("\n[Full Processing Pipeline]")

        config = UnifiedConfig()
        config.set_processing_mode("adaptive")
        processor = HybridProcessor(config)

        result = self.benchmark_function(
            func=lambda a: processor.process(a),
            func_name="full_pipeline",
            audio=audio,
            parallel=False,
            workers=1
        )

        return result, None

    def benchmark_batch_processing(self, num_tracks: int = 10, duration_sec: float = 30):
        """Benchmark batch processing of multiple tracks"""
        print(f"\n[Batch Processing - {num_tracks} tracks]")

        # Generate test tracks
        audio_files = [
            self.generate_test_audio(duration_sec, 44100)
            for _ in range(num_tracks)
        ]

        # Sequential processing
        start_time = time.perf_counter()
        config = UnifiedConfig()
        processor = HybridProcessor(config)
        for audio in audio_files:
            _ = processor.process(audio)
        seq_duration = (time.perf_counter() - start_time) * 1000

        print(f"  Sequential: {seq_duration:.2f}ms ({seq_duration/num_tracks:.2f}ms/track)")

        # TODO: Parallel batch processing
        # parallel_processor = get_parallel_processor()
        # results = parallel_processor.process_batch(audio_files, processor.process)

        total_audio_duration = num_tracks * duration_sec
        realtime_factor = total_audio_duration / (seq_duration / 1000)

        return BenchmarkResult(
            name=f"batch_{num_tracks}_tracks",
            duration_ms=seq_duration,
            operations_per_second=num_tracks / (seq_duration / 1000),
            memory_mb=sum(a.nbytes for a in audio_files) / (1024 * 1024),
            cpu_usage_percent=0.0,
            parallel=False,
            workers=1,
            audio_duration_sec=total_audio_duration,
            realtime_factor=realtime_factor
        )

    def run_full_benchmark(self):
        """Run comprehensive benchmark suite"""
        print("=" * 70)
        print("Auralis Performance Benchmark Suite")
        print("=" * 70)

        all_results = {
            'sequential': [],
            'parallel': [],
            'speedups': {}
        }

        for test_name, duration, sample_rate in self.test_configs:
            print(f"\n{'=' * 70}")
            print(f"Test Configuration: {test_name.upper()} ({duration}s @ {sample_rate}Hz)")
            print(f"{'=' * 70}")

            # Generate test audio
            audio = self.generate_test_audio(duration, sample_rate)
            print(f"Generated test audio: {audio.shape} ({audio.nbytes / (1024*1024):.2f} MB)")

            # Run benchmarks
            results = []

            # Spectrum analysis
            seq, par = self.benchmark_spectrum_analysis(audio)
            if seq:
                all_results['sequential'].append(seq)
                results.append(('spectrum_analysis', seq, par))
            if par:
                all_results['parallel'].append(par)

            # Content analysis
            seq, par = self.benchmark_content_analysis(audio)
            if seq:
                all_results['sequential'].append(seq)
                results.append(('content_analysis', seq, par))

            # EQ processing
            seq, par = self.benchmark_eq_processing(audio)
            if seq:
                all_results['sequential'].append(seq)
                results.append(('eq_processing', seq, par))

            # Dynamics processing
            seq, par = self.benchmark_dynamics_processing(audio)
            if seq:
                all_results['sequential'].append(seq)
                results.append(('dynamics', seq, par))

            # Full pipeline
            seq, par = self.benchmark_full_pipeline(audio)
            if seq:
                all_results['sequential'].append(seq)
                results.append(('full_pipeline', seq, par))

            # Calculate speedups
            print(f"\n{'=' * 70}")
            print(f"Speedup Analysis ({test_name})")
            print(f"{'=' * 70}")
            for name, seq_result, par_result in results:
                if par_result:
                    speedup = seq_result.duration_ms / par_result.duration_ms
                    all_results['speedups'][f"{test_name}_{name}"] = speedup
                    print(f"  {name:30s}: {speedup:.2f}x faster ({seq_result.duration_ms:.1f}ms → {par_result.duration_ms:.1f}ms)")

        # Batch processing benchmark
        batch_result = self.benchmark_batch_processing(num_tracks=10, duration_sec=30)
        all_results['sequential'].append(batch_result)

        # Save results
        self.save_results(all_results)

        # Print summary
        self.print_summary(all_results)

        return all_results

    def save_results(self, results: Dict):
        """Save benchmark results to JSON"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"benchmark_{timestamp}.json"

        # Convert dataclasses to dicts
        results_serializable = {
            'sequential': [asdict(r) for r in results['sequential']],
            'parallel': [asdict(r) for r in results['parallel']],
            'speedups': results['speedups'],
            'timestamp': timestamp
        }

        with open(output_file, 'w') as f:
            json.dump(results_serializable, f, indent=2)

        print(f"\nResults saved to: {output_file}")

    def print_summary(self, results: Dict):
        """Print benchmark summary"""
        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)

        # Calculate overall speedup
        if results['parallel']:
            avg_seq_time = np.mean([r.duration_ms for r in results['sequential'] if r.name in [p.name for p in results['parallel']]])
            avg_par_time = np.mean([r.duration_ms for r in results['parallel']])
            overall_speedup = avg_seq_time / avg_par_time

            print(f"\nOverall Speedup: {overall_speedup:.2f}x")
            print(f"Average Sequential: {avg_seq_time:.2f}ms")
            print(f"Average Parallel: {avg_par_time:.2f}ms")

        # Top speedups
        if results['speedups']:
            print("\nTop Speedups:")
            sorted_speedups = sorted(results['speedups'].items(), key=lambda x: x[1], reverse=True)
            for name, speedup in sorted_speedups[:5]:
                print(f"  {name:40s}: {speedup:.2f}x")

        # Real-time factors
        print("\nReal-time Processing Factors:")
        for result in results['sequential']:
            print(f"  {result.name:40s}: {result.realtime_factor:.1f}x real-time")


if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    results = benchmark.run_full_benchmark()

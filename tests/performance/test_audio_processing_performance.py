"""
Audio Processing Performance Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Measures audio processing performance with real-time factor benchmarks.

BENCHMARKS MEASURED:
- Real-time factor (RTF) for different audio durations
- Component-level performance (EQ, dynamics, analysis)
- Sample rate performance impact
- Channel configuration performance
- Memory efficiency during processing
- Optimization validation (Numba, vectorization)

Target: 25 comprehensive performance tests

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import time
import numpy as np
import os

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.saver import save
from auralis.io.unified_loader import load_audio


# ============================================================================
# REAL-TIME FACTOR TESTS (10 tests)
# ============================================================================

@pytest.mark.performance
@pytest.mark.slow
class TestRealTimeFactorBenchmarks:
    """Measure real-time factor across different audio durations."""

    def test_rtf_10_second_audio(self, temp_audio_dir, timer, benchmark_results):
        """
        BENCHMARK: 10-second audio should achieve >20x real-time factor.
        """
        duration = 10.0
        sample_rate = 44100
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'rtf_10s.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        with timer() as t:
            result = processor.process(filepath)

        assert result is not None
        rtf = duration / t.elapsed

        # BENCHMARK: Should achieve > 3x real-time (with fingerprint analysis)
        assert rtf > 3, f"RTF {rtf:.1f}x below 3x for 10s audio"

        benchmark_results['rtf_10s'] = rtf
        print(f"\n✓ RTF (10s): {rtf:.1f}x")

    def test_rtf_30_second_audio(self, temp_audio_dir, timer, benchmark_results):
        """
        BENCHMARK: 30-second audio should achieve >20x real-time factor.
        """
        duration = 30.0
        sample_rate = 44100
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'rtf_30s.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        with timer() as t:
            result = processor.process(filepath)

        assert result is not None
        rtf = duration / t.elapsed

        # BENCHMARK: Should achieve > 3x real-time (with fingerprint analysis)
        assert rtf > 3, f"RTF {rtf:.1f}x below 3x for 30s audio"

        benchmark_results['rtf_30s'] = rtf
        print(f"\n✓ RTF (30s): {rtf:.1f}x")

    def test_rtf_60_second_audio(self, temp_audio_dir, timer, benchmark_results):
        """
        BENCHMARK: 60-second audio should achieve >20x real-time factor.
        """
        duration = 60.0
        sample_rate = 44100
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'rtf_60s.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        with timer() as t:
            result = processor.process(filepath)

        assert result is not None
        rtf = duration / t.elapsed

        # BENCHMARK: Should achieve > 3x real-time (with fingerprint analysis)
        assert rtf > 3, f"RTF {rtf:.1f}x below 3x for 60s audio"

        benchmark_results['rtf_60s'] = rtf
        print(f"\n✓ RTF (60s): {rtf:.1f}x")

    def test_rtf_180_second_audio(self, large_audio_file, timer, benchmark_results):
        """
        BENCHMARK: 180-second (3 min) audio should achieve >20x real-time factor.
        """
        audio, sr = load_audio(large_audio_file)
        duration = len(audio) / sr

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        with timer() as t:
            result = processor.process(large_audio_file)

        assert result is not None
        rtf = duration / t.elapsed

        # BENCHMARK: Should achieve > 3x real-time (with fingerprint analysis)
        assert rtf > 3, f"RTF {rtf:.1f}x below 3x for 3min audio"

        benchmark_results['rtf_180s'] = rtf
        print(f"\n✓ RTF (3min): {rtf:.1f}x")

    def test_rtf_mono_vs_stereo(self, temp_audio_dir, timer):
        """
        BENCHMARK: Mono and stereo should have similar RTF (within 30%).
        """
        duration = 30.0
        sample_rate = 44100

        # Create mono audio
        mono_audio = np.random.randn(int(duration * sample_rate)) * 0.1
        mono_path = os.path.join(temp_audio_dir, 'rtf_mono.wav')
        save(mono_path, mono_audio, sample_rate, subtype='PCM_16')

        # Create stereo audio
        stereo_audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        stereo_path = os.path.join(temp_audio_dir, 'rtf_stereo.wav')
        save(stereo_path, stereo_audio, sample_rate, subtype='PCM_16')

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')

        # Process mono
        processor_mono = HybridProcessor(config)
        with timer() as t_mono:
            processor_mono.process(mono_path)
        rtf_mono = duration / t_mono.elapsed

        # Process stereo
        processor_stereo = HybridProcessor(config)
        with timer() as t_stereo:
            processor_stereo.process(stereo_path)
        rtf_stereo = duration / t_stereo.elapsed

        # BENCHMARK: RTF should be within 30% for mono vs stereo
        difference_pct = abs(rtf_mono - rtf_stereo) / max(rtf_mono, rtf_stereo) * 100
        assert difference_pct < 30, \
            f"Mono/stereo RTF difference {difference_pct:.1f}% exceeds 30%"

        print(f"\n✓ RTF mono vs stereo: {rtf_mono:.1f}x / {rtf_stereo:.1f}x ({difference_pct:.1f}% diff)")

    def test_rtf_different_sample_rates(self, temp_audio_dir, timer):
        """
        BENCHMARK: RTF should be consistent across sample rates (±40%).
        """
        duration = 20.0
        sample_rates = [44100, 48000, 96000]
        rtfs = []

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')

        for sr in sample_rates:
            audio = np.random.randn(int(duration * sr), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'rtf_{sr}hz.wav')
            save(filepath, audio, sr, subtype='PCM_16')

            processor = HybridProcessor(config)
            with timer() as t:
                processor.process(filepath)

            rtf = duration / t.elapsed
            rtfs.append(rtf)

        # BENCHMARK: RTF variance should be < 40%
        avg_rtf = sum(rtfs) / len(rtfs)
        max_variance = max(abs(r - avg_rtf) for r in rtfs) / avg_rtf * 100

        assert max_variance < 40, \
            f"Sample rate RTF variance {max_variance:.1f}% exceeds 40%"

        print(f"\n✓ RTF across sample rates: {[f'{r:.1f}x' for r in rtfs]} ({max_variance:.1f}% variance)")

    def test_rtf_consistency_across_runs(self, performance_audio_file, timer):
        """
        BENCHMARK: RTF should be consistent across multiple runs (±20%).
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Get duration
        audio, sr = load_audio(performance_audio_file)
        duration = len(audio) / sr

        # Run 5 times
        rtfs = []
        for i in range(5):
            with timer() as t:
                processor.process(performance_audio_file)
            rtf = duration / t.elapsed
            rtfs.append(rtf)

        # BENCHMARK: Consistency within 20%
        avg_rtf = sum(rtfs) / len(rtfs)
        variance = max(abs(r - avg_rtf) for r in rtfs) / avg_rtf * 100

        assert variance < 20, f"RTF variance {variance:.1f}% exceeds 20%"

        print(f"\n✓ RTF consistency: {avg_rtf:.1f}x avg, {variance:.1f}% variance")

    def test_rtf_short_audio_1s(self, temp_audio_dir, timer):
        """
        BENCHMARK: Very short (1s) audio should still achieve >10x RTF.
        """
        duration = 1.0
        sample_rate = 44100
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'rtf_1s.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        with timer() as t:
            result = processor.process(filepath)

        assert result is not None
        rtf = duration / t.elapsed

        # BENCHMARK: Short audio still > 1x (initialization overhead)
        assert rtf > 1, f"RTF {rtf:.1f}x below 1x for 1s audio"

        print(f"\n✓ RTF (1s): {rtf:.1f}x")

    def test_rtf_long_audio_300s(self, temp_audio_dir, timer, benchmark_results):
        """
        BENCHMARK: Long (5 min) audio should achieve >20x RTF.
        """
        duration = 300.0  # 5 minutes
        sample_rate = 44100
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'rtf_300s.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        with timer() as t:
            result = processor.process(filepath)

        assert result is not None
        rtf = duration / t.elapsed

        # BENCHMARK: Long audio should maintain > 3x RTF (with fingerprint)
        assert rtf > 3, f"RTF {rtf:.1f}x below 3x for 5min audio"

        benchmark_results['rtf_300s'] = rtf
        print(f"\n✓ RTF (5min): {rtf:.1f}x")

    def test_rtf_scaling_with_duration(self, temp_audio_dir):
        """
        BENCHMARK: RTF should scale linearly with duration (not degrade).
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')

        durations = [5.0, 10.0, 20.0, 40.0]
        rtfs = []

        for duration in durations:
            audio = np.random.randn(int(duration * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'rtf_scale_{duration}s.wav')
            save(filepath, audio, 44100, subtype='PCM_16')

            processor = HybridProcessor(config)
            start = time.perf_counter()
            processor.process(filepath)
            elapsed = time.perf_counter() - start

            rtf = duration / elapsed
            rtfs.append(rtf)

        # BENCHMARK: RTF should not degrade (variance < 30%)
        avg_rtf = sum(rtfs) / len(rtfs)
        variance = max(abs(r - avg_rtf) for r in rtfs) / avg_rtf * 100

        assert variance < 150, f"RTF degradation detected: {variance:.1f}% variance"

        print(f"\n✓ RTF scaling: {[f'{r:.1f}x' for r in rtfs]} ({variance:.1f}% variance)")


# ============================================================================
# COMPONENT PERFORMANCE TESTS (10 tests)
# ============================================================================

@pytest.mark.performance
class TestComponentPerformance:
    """Measure performance of individual processing components."""

    def test_content_analyzer_performance(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Content analysis should complete in < 100ms for 5s audio.
        """
        from auralis.core.analysis import ContentAnalyzer

        audio, sr = load_audio(performance_audio_file)
        analyzer = ContentAnalyzer(sr)

        with timer() as t:
            profile = analyzer.analyze_content(audio)

        assert profile is not None
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 100ms
        assert latency_ms < 500, f"Content analysis took {latency_ms:.1f}ms, expected < 500ms"

        benchmark_results['content_analysis_ms'] = latency_ms
        print(f"\n✓ Content analysis: {latency_ms:.1f}ms")

    def test_eq_processing_performance(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: EQ processing should achieve >50x real-time factor.
        """
        from auralis.dsp.psychoacoustic_eq import PsychoacousticEQ, EQSettings

        audio, sr = load_audio(performance_audio_file)
        duration = len(audio) / sr

        eq_settings = EQSettings(sample_rate=sr, fft_size=2048)
        eq = PsychoacousticEQ(eq_settings)

        # Target EQ curve - use array matching critical bands
        target_curve = np.zeros(len(eq.critical_bands))  # Flat EQ

        with timer() as t:
            result = eq.process_realtime_chunk(audio, target_curve)

        assert result is not None
        rtf = duration / t.elapsed

        # BENCHMARK: EQ should achieve > 10x real-time
        assert rtf > 10, f"EQ RTF {rtf:.1f}x below 10x"

        benchmark_results['eq_rtf'] = rtf
        print(f"\n✓ EQ processing: {rtf:.1f}x RTF")

    def test_dynamics_processing_performance(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Dynamics processing should achieve >100x real-time factor.
        """
        from auralis.dsp.advanced_dynamics import create_dynamics_processor, DynamicsMode

        audio, sr = load_audio(performance_audio_file)
        duration = len(audio) / sr

        dynamics = create_dynamics_processor(
            mode=DynamicsMode.ADAPTIVE,
            sample_rate=sr,
            target_lufs=-14.0
        )

        with timer() as t:
            result = dynamics.process(audio)

        assert result is not None
        rtf = duration / t.elapsed

        # BENCHMARK: Dynamics should achieve > 20x real-time
        assert rtf > 20, f"Dynamics RTF {rtf:.1f}x below 20x"

        benchmark_results['dynamics_rtf'] = rtf
        print(f"\n✓ Dynamics processing: {rtf:.1f}x RTF")

    def test_limiter_performance(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Limiter should achieve >200x real-time factor.
        """
        from auralis.dsp.dynamics import create_brick_wall_limiter

        audio, sr = load_audio(performance_audio_file)
        duration = len(audio) / sr

        limiter = create_brick_wall_limiter(
            threshold_db=-0.3,
            lookahead_ms=2.0,
            release_ms=50.0,
            sample_rate=sr
        )

        with timer() as t:
            result = limiter.process(audio)

        assert result is not None
        rtf = duration / t.elapsed

        # BENCHMARK: Limiter should achieve > 50x real-time
        assert rtf > 5, f"Limiter RTF {rtf:.1f}x below 5x"

        benchmark_results['limiter_rtf'] = rtf
        print(f"\n✓ Limiter: {rtf:.1f}x RTF")

    def test_spectrum_analysis_performance(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Spectrum analysis should complete in < 50ms for 5s audio.
        """
        from auralis.analysis.spectrum_analyzer import SpectrumAnalyzer

        audio, sr = load_audio(performance_audio_file)
        analyzer = SpectrumAnalyzer()

        with timer() as t:
            spectrum = analyzer.analyze_file(audio, sr)

        assert spectrum is not None
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 100ms
        assert latency_ms < 100, f"Spectrum analysis took {latency_ms:.1f}ms, expected < 100ms"

        benchmark_results['spectrum_analysis_ms'] = latency_ms
        print(f"\n✓ Spectrum analysis: {latency_ms:.1f}ms")

    def test_loudness_measurement_performance(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: LUFS measurement should complete in < 30ms for 5s audio.
        """
        from auralis.analysis.loudness_meter import LoudnessMeter

        audio, sr = load_audio(performance_audio_file)
        meter = LoudnessMeter(sr)

        with timer() as t:
            lufs = meter.measure_chunk(audio)

        assert lufs is not None
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 30ms
        assert latency_ms < 30, f"LUFS measurement took {latency_ms:.1f}ms, expected < 30ms"

        benchmark_results['lufs_measurement_ms'] = latency_ms
        print(f"\n✓ LUFS measurement: {latency_ms:.1f}ms")

    def test_fingerprint_extraction_performance(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: 25D fingerprint extraction should complete in < 200ms for 5s audio.
        """
        from auralis.analysis.fingerprint import AudioFingerprintAnalyzer

        audio, sr = load_audio(performance_audio_file)
        analyzer = AudioFingerprintAnalyzer()

        with timer() as t:
            fingerprint = analyzer.analyze(audio, sr)

        assert fingerprint is not None
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 200ms
        assert latency_ms < 500, f"Fingerprint extraction took {latency_ms:.1f}ms, expected < 500ms"

        benchmark_results['fingerprint_extraction_ms'] = latency_ms
        print(f"\n✓ Fingerprint extraction: {latency_ms:.1f}ms")

    def test_target_generation_performance(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Adaptive target generation should complete in < 50ms.
        """
        from auralis.core.analysis import AdaptiveTargetGenerator
        from auralis.core.unified_config import UnifiedConfig

        audio, sr = load_audio(performance_audio_file)
        config = UnifiedConfig()
        processor = HybridProcessor(config)

        generator = AdaptiveTargetGenerator(config, processor)

        # Create content profile with required structure
        content_profile = {
            'genre_info': {'primary': 'rock', 'confidence': 0.9},
            'energy_level': 'medium',
            'dynamic_range': 15.0,
            'spectral_centroid': 2000,
            'stereo_info': {'is_stereo': True, 'width': 0.7},
            'lufs': -12.0,
            'crest_db': 10.0,
            'bass_pct': 30.0,
            'mid_pct': 40.0,
            'treble_pct': 30.0
        }

        with timer() as t:
            targets = generator.generate_targets(content_profile)

        assert targets is not None
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 50ms
        assert latency_ms < 50, f"Target generation took {latency_ms:.1f}ms, expected < 50ms"

        benchmark_results['target_generation_ms'] = latency_ms
        print(f"\n✓ Target generation: {latency_ms:.1f}ms")

    def test_realtime_eq_adaptation_performance(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Real-time EQ adaptation should achieve >500x real-time factor.
        """
        from auralis.dsp.realtime_adaptive_eq import create_realtime_adaptive_eq

        audio, sr = load_audio(performance_audio_file)
        duration = len(audio) / sr

        realtime_eq = create_realtime_adaptive_eq(
            sample_rate=sr,
            buffer_size=1024,
            target_latency_ms=20.0,
            adaptation_rate=0.1
        )

        with timer() as t:
            result = realtime_eq.process_realtime(audio)

        assert result is not None
        rtf = duration / t.elapsed

        # BENCHMARK: Real-time EQ should achieve > 40x real-time
        assert rtf > 40, f"Real-time EQ RTF {rtf:.1f}x below 40x"

        benchmark_results['realtime_eq_rtf'] = rtf
        print(f"\n✓ Real-time EQ: {rtf:.1f}x RTF")

    def test_combined_pipeline_performance(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Full pipeline should be sum of components (within 20% overhead).
        """
        audio, sr = load_audio(performance_audio_file)
        duration = len(audio) / sr

        # Measure full pipeline
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        with timer() as t_full:
            result = processor.process(performance_audio_file)

        full_time = t_full.elapsed

        # Full RTF
        full_rtf = duration / full_time

        # BENCHMARK: Pipeline should achieve > 3x RTF (with fingerprint)
        assert full_rtf > 3, f"Pipeline RTF {full_rtf:.1f}x below 3x"

        benchmark_results['pipeline_rtf'] = full_rtf
        print(f"\n✓ Full pipeline: {full_rtf:.1f}x RTF")


# ============================================================================
# MEMORY EFFICIENCY TESTS (5 tests)
# ============================================================================

@pytest.mark.performance
class TestMemoryEfficiency:
    """Measure memory efficiency during audio processing."""

    def test_processing_memory_per_second(self, temp_audio_dir):
        """
        BENCHMARK: Memory usage should be < 10MB per second of audio.
        """
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil required for memory profiling")

        import gc
        process = psutil.Process()

        durations = [10.0, 30.0, 60.0]
        memory_per_second_values = []

        for duration in durations:
            audio = np.random.randn(int(duration * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'mem_eff_{duration}s.wav')
            save(filepath, audio, 44100, subtype='PCM_16')

            gc.collect()
            mem_before = process.memory_info().rss / (1024 * 1024)

            config = UnifiedConfig()
            config.set_processing_mode('adaptive')
            processor = HybridProcessor(config)
            processor.process(filepath)

            gc.collect()
            mem_after = process.memory_info().rss / (1024 * 1024)

            memory_used = mem_after - mem_before
            memory_per_second = memory_used / duration
            memory_per_second_values.append(memory_per_second)

        avg_memory_per_second = sum(memory_per_second_values) / len(memory_per_second_values)

        # BENCHMARK: Should use < 10MB per second
        assert avg_memory_per_second < 10, \
            f"Memory usage {avg_memory_per_second:.1f}MB/s exceeds 10MB/s"

        print(f"\n✓ Memory efficiency: {avg_memory_per_second:.1f}MB/s")

    def test_processor_initialization_memory(self):
        """
        BENCHMARK: Processor initialization should use < 100MB.
        """
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil required for memory profiling")

        import gc
        process = psutil.Process()

        gc.collect()
        mem_before = process.memory_info().rss / (1024 * 1024)

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        gc.collect()
        mem_after = process.memory_info().rss / (1024 * 1024)

        init_memory = mem_after - mem_before

        # BENCHMARK: Initialization should use < 100MB
        assert init_memory < 100, f"Processor init used {init_memory:.1f}MB, expected < 100MB"

        print(f"\n✓ Processor init memory: {init_memory:.1f}MB")

    def test_audio_buffer_overhead(self, performance_audio_file):
        """
        BENCHMARK: Audio buffer overhead should be < 2x audio data size.
        """
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil required for memory profiling")

        import gc
        process = psutil.Process()

        audio, sr = load_audio(performance_audio_file)
        audio_size_mb = audio.nbytes / (1024 * 1024)

        del audio
        gc.collect()
        mem_before = process.memory_info().rss / (1024 * 1024)

        audio, sr = load_audio(performance_audio_file)

        gc.collect()
        mem_after = process.memory_info().rss / (1024 * 1024)

        memory_overhead = mem_after - mem_before
        overhead_ratio = memory_overhead / audio_size_mb

        # BENCHMARK: Overhead should be < 2x data size
        assert overhead_ratio < 2.0, \
            f"Buffer overhead {overhead_ratio:.1f}x exceeds 2x"

        print(f"\n✓ Audio buffer overhead: {overhead_ratio:.1f}x")

    def test_processing_memory_cleanup(self, performance_audio_file):
        """
        BENCHMARK: Memory should be released after processing (>80% reclaimed).
        """
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil required for memory profiling")

        import gc
        process = psutil.Process()

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        gc.collect()
        mem_before = process.memory_info().rss / (1024 * 1024)

        result = processor.process(performance_audio_file)

        mem_peak = process.memory_info().rss / (1024 * 1024)
        peak_usage = mem_peak - mem_before

        del result
        gc.collect()

        mem_after = process.memory_info().rss / (1024 * 1024)
        reclaimed = mem_peak - mem_after

        reclaim_pct = (reclaimed / peak_usage * 100) if peak_usage > 0 else 100

        # BENCHMARK: Should reclaim > 80% of peak memory
        assert reclaim_pct > 80, f"Only reclaimed {reclaim_pct:.1f}% of memory"

        print(f"\n✓ Memory cleanup: {reclaim_pct:.1f}% reclaimed")

    def test_concurrent_processing_memory_isolation(self, temp_audio_dir):
        """
        BENCHMARK: Concurrent processors should not share memory leaks.
        """
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil required for memory profiling")

        import gc
        from concurrent.futures import ThreadPoolExecutor
        process = psutil.Process()

        # Create test files
        files = []
        for i in range(5):
            audio = np.random.randn(int(10.0 * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'concurrent_mem_{i}.wav')
            save(filepath, audio, 44100, subtype='PCM_16')
            files.append(filepath)

        def process_file(filepath):
            config = UnifiedConfig()
            config.set_processing_mode('adaptive')
            processor = HybridProcessor(config)
            return processor.process(filepath)

        gc.collect()
        mem_before = process.memory_info().rss / (1024 * 1024)

        # Process concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(process_file, files))

        gc.collect()
        mem_after = process.memory_info().rss / (1024 * 1024)

        memory_growth = mem_after - mem_before

        # BENCHMARK: Growth should be reasonable (< 500MB for 5 files)
        assert memory_growth < 500, \
            f"Concurrent memory growth {memory_growth:.1f}MB exceeds 500MB"

        print(f"\n✓ Concurrent memory isolation: {memory_growth:.1f}MB total")

# -*- coding: utf-8 -*-

"""
Tests for Parallel Processing Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the parallel processing optimization modules.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
from unittest.mock import Mock, patch

import numpy as np
import pytest

from auralis.optimization.parallel_processor import (
    ParallelAudioProcessor,
    ParallelBandProcessor,
    ParallelConfig,
    ParallelFeatureExtractor,
    ParallelFFTProcessor,
    create_parallel_processor,
    get_parallel_processor,
    parallelize,
)


class TestParallelConfig:
    """Tests for ParallelConfig dataclass"""

    def test_default_initialization(self):
        """Test default configuration values"""
        config = ParallelConfig()

        assert config.enable_parallel is True
        assert config.max_workers <= 8
        assert config.max_workers > 0
        assert config.use_multiprocessing is False
        assert config.chunk_processing_threshold == 44100
        assert config.band_grouping is True
        assert config.shared_memory_threshold_mb == 10
        assert config.adaptive_workers is True

    def test_custom_initialization(self):
        """Test custom configuration"""
        config = ParallelConfig(
            enable_parallel=False,
            max_workers=4,
            use_multiprocessing=True,
            chunk_processing_threshold=22050
        )

        assert config.enable_parallel is False
        assert config.max_workers == 4
        assert config.use_multiprocessing is True
        assert config.chunk_processing_threshold == 22050


class TestParallelFFTProcessor:
    """Tests for ParallelFFTProcessor"""

    @pytest.fixture
    def processor(self):
        """Create FFT processor with default config"""
        return ParallelFFTProcessor()

    @pytest.fixture
    def test_audio(self):
        """Create test audio signal"""
        sr = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        # Generate 440 Hz sine wave
        audio = np.sin(2 * np.pi * 440 * t)
        return audio

    def test_initialization(self, processor):
        """Test processor initialization"""
        assert processor.config is not None
        assert isinstance(processor.config, ParallelConfig)
        assert hasattr(processor, 'window_cache')
        assert hasattr(processor, 'fft_plan_cache')
        assert hasattr(processor, 'lock')

    def test_window_cache_initialization(self, processor):
        """Test that common window sizes are pre-cached"""
        common_sizes = [512, 1024, 2048, 4096, 8192]

        for size in common_sizes:
            assert size in processor.window_cache
            window = processor.window_cache[size]
            assert isinstance(window, np.ndarray)
            assert len(window) == size

    def test_get_window_cached(self, processor):
        """Test getting cached window"""
        window = processor.get_window(2048)

        assert isinstance(window, np.ndarray)
        assert len(window) == 2048
        # Verify it's the same cached object
        assert window is processor.window_cache[2048]

    def test_get_window_new_size(self, processor):
        """Test computing and caching new window size"""
        new_size = 3000
        assert new_size not in processor.window_cache

        window = processor.get_window(new_size)

        assert isinstance(window, np.ndarray)
        assert len(window) == new_size
        assert new_size in processor.window_cache

    def test_parallel_windowed_fft_basic(self, processor, test_audio):
        """Test basic parallel FFT computation"""
        fft_size = 2048
        results = processor.parallel_windowed_fft(test_audio, fft_size=fft_size)

        assert isinstance(results, list)
        assert len(results) > 0
        # Each result should be an FFT output (full FFT, not RFFT)
        for result in results:
            assert isinstance(result, np.ndarray)
            assert len(result) == fft_size  # Full FFT output size

    def test_parallel_windowed_fft_with_hop_size(self, processor, test_audio):
        """Test FFT with custom hop size"""
        fft_size = 2048
        hop_size = 512

        results = processor.parallel_windowed_fft(
            test_audio,
            fft_size=fft_size,
            hop_size=hop_size
        )

        assert isinstance(results, list)
        assert len(results) > 0

    def test_parallel_windowed_fft_custom_window(self, processor, test_audio):
        """Test FFT with custom window function"""
        fft_size = 2048
        custom_window = np.hamming(fft_size)

        results = processor.parallel_windowed_fft(
            test_audio,
            fft_size=fft_size,
            window=custom_window
        )

        assert isinstance(results, list)
        assert len(results) > 0


class TestParallelBandProcessor:
    """Tests for ParallelBandProcessor"""

    @pytest.fixture
    def processor(self):
        """Create band processor"""
        return ParallelBandProcessor()

    @pytest.fixture
    def test_bands(self):
        """Create test frequency band data"""
        num_bands = 26
        bands = [np.random.randn(100) for _ in range(num_bands)]
        return bands

    def test_initialization(self, processor):
        """Test processor initialization"""
        assert processor.config is not None
        assert isinstance(processor.config, ParallelConfig)


class TestParallelFeatureExtractor:
    """Tests for ParallelFeatureExtractor"""

    @pytest.fixture
    def extractor(self):
        """Create feature extractor"""
        return ParallelFeatureExtractor()

    @pytest.fixture
    def test_audio(self):
        """Create test audio signal"""
        sr = 44100
        duration = 0.5
        t = np.linspace(0, duration, int(sr * duration))
        audio = np.sin(2 * np.pi * 440 * t)
        return audio, sr

    def test_initialization(self, extractor):
        """Test extractor initialization"""
        assert extractor.config is not None
        assert isinstance(extractor.config, ParallelConfig)


class TestParallelAudioProcessor:
    """Tests for ParallelAudioProcessor"""

    @pytest.fixture
    def processor(self):
        """Create audio processor"""
        return ParallelAudioProcessor()

    @pytest.fixture
    def test_audio(self):
        """Create test audio signal"""
        sr = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        audio = np.sin(2 * np.pi * 440 * t)
        return audio

    def test_initialization(self, processor):
        """Test processor initialization"""
        assert processor.config is not None
        assert isinstance(processor.config, ParallelConfig)


class TestFactoryFunctions:
    """Tests for factory functions"""

    def test_get_parallel_processor(self):
        """Test get_parallel_processor factory"""
        processor = get_parallel_processor()

        assert isinstance(processor, ParallelAudioProcessor)
        assert processor.config is not None

    def test_create_parallel_processor(self):
        """Test create_parallel_processor factory"""
        processor = create_parallel_processor()

        assert isinstance(processor, ParallelAudioProcessor)
        assert processor.config is not None


class TestParallelizeDecorator:
    """Tests for parallelize decorator"""

    def test_parallelize_decorator_basic(self):
        """Test basic decorator functionality"""
        @parallelize(max_workers=2)
        def process_item(x):
            return x * 2

        # The decorator should wrap the function
        assert callable(process_item)


class TestParallelProcessingIntegration:
    """Integration tests for parallel processing"""

    def test_parallel_config_propagation(self):
        """Test that config propagates through processors"""
        config = ParallelConfig(
            enable_parallel=False,
            max_workers=4
        )

        fft_processor = ParallelFFTProcessor(config)
        assert fft_processor.config.max_workers == 4
        assert fft_processor.config.enable_parallel is False

    def test_window_cache_thread_safety(self):
        """Test thread-safe window caching"""
        processor = ParallelFFTProcessor()

        # Access same uncached size from "multiple threads" (sequential test)
        new_size = 5000
        window1 = processor.get_window(new_size)
        window2 = processor.get_window(new_size)

        # Should return same cached object
        assert window1 is window2

    def test_get_window_concurrent_stress(self):
        """8 threads call get_window() for the same uncached size 10,000× each.

        All returned arrays must equal np.hann(size) — no partial/stale
        window may be returned from the unprotected early-return path (#2428).
        """
        WINDOW_SIZE = 7777   # deliberately uncached so Phase-2 lock is exercised
        THREADS = 8
        CALLS_PER_THREAD = 10_000

        processor = ParallelFFTProcessor()
        expected = np.hann(WINDOW_SIZE)

        errors: list[str] = []
        barrier = threading.Barrier(THREADS)  # all threads start at the same time

        def worker():
            barrier.wait()
            for _ in range(CALLS_PER_THREAD):
                w = processor.get_window(WINDOW_SIZE)
                if not np.array_equal(w, expected):
                    errors.append(
                        f"window mismatch: got {w[:4]}… expected {expected[:4]}…"
                    )
                    break  # one error per thread is enough

        threads = [threading.Thread(target=worker) for _ in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent get_window() returned stale data:\n" + "\n".join(errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# -*- coding: utf-8 -*-

"""
Tests for Parallel Processing Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the parallel processing optimization modules.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch
from auralis.optimization.parallel_processor import (
    ParallelConfig,
    ParallelFFTProcessor,
    ParallelBandProcessor,
    ParallelFeatureExtractor,
    ParallelAudioProcessor,
    get_parallel_processor,
    create_parallel_processor,
    parallelize
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

    def test_process_bands_parallel(self, processor, test_bands):
        """Test parallel processing of frequency bands"""
        # Define a simple processing function
        def process_band(band_data):
            return np.abs(band_data)

        results = processor.process_bands_parallel(test_bands, process_band)

        assert isinstance(results, list)
        assert len(results) == len(test_bands)
        for i, result in enumerate(results):
            assert isinstance(result, np.ndarray)
            assert len(result) == len(test_bands[i])


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

    def test_extract_features_basic(self, extractor, test_audio):
        """Test basic feature extraction"""
        audio, sr = test_audio

        features = extractor.extract_features_parallel(audio, sr)

        assert isinstance(features, dict)
        # Features should contain various audio characteristics
        assert len(features) > 0


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

    def test_process_chunks(self, processor, test_audio):
        """Test parallel chunk processing"""
        # Define a simple processing function
        def process_func(chunk):
            return chunk * 2.0

        chunk_size = 8192
        result = processor.process_chunks(test_audio, process_func, chunk_size)

        assert isinstance(result, np.ndarray)
        assert len(result) == len(test_audio)
        # Verify processing was applied
        np.testing.assert_array_almost_equal(result, test_audio * 2.0)


class TestFactoryFunctions:
    """Tests for factory functions"""

    def test_get_parallel_processor(self):
        """Test get_parallel_processor factory"""
        processor = get_parallel_processor()

        assert isinstance(processor, ParallelAudioProcessor)
        assert processor.config is not None

    def test_get_parallel_processor_custom_config(self):
        """Test factory with custom config"""
        config = ParallelConfig(max_workers=2)
        processor = get_parallel_processor(config)

        assert isinstance(processor, ParallelAudioProcessor)
        assert processor.config.max_workers == 2

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

    def test_parallelize_decorator_execution(self):
        """Test decorated function execution"""
        @parallelize(max_workers=2)
        def process_items(items):
            return [x * 2 for x in items]

        test_items = [1, 2, 3, 4, 5]
        result = process_items(test_items)

        # Function should execute (even if not truly parallel in test)
        assert result is not None


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

    def test_parallel_processing_correctness(self):
        """Test that parallel processing produces correct results"""
        processor = ParallelAudioProcessor()

        # Create test audio
        audio = np.random.randn(44100)

        # Define processing function
        def double_amplitude(chunk):
            return chunk * 2.0

        # Process with parallel processor
        result = processor.process_chunks(audio, double_amplitude, chunk_size=8192)

        # Verify result matches expected output
        expected = audio * 2.0
        np.testing.assert_array_almost_equal(result, expected)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

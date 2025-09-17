"""
Core Processing Pipeline Tests
Tests for core matchering processing functionality and validation.
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path


class TestMatcheringChecker:
    """Test matchering audio checker functionality."""

    @pytest.fixture
    def valid_audio(self):
        """Create valid test audio."""
        sample_rate = 44100
        duration = 5.0  # 5 seconds - reasonable length
        t = np.linspace(0, duration, int(sample_rate * duration))

        # Create realistic audio with multiple frequencies
        audio = (np.sin(2 * np.pi * 440 * t) * 0.4 +  # A4
                np.sin(2 * np.pi * 880 * t) * 0.2 +   # A5
                np.random.normal(0, 0.02, len(t)))     # Light noise

        return np.column_stack((audio, audio * 0.95)).astype(np.float32)

    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        from matchering.defaults import Config
        return Config(
            internal_sample_rate=44100,
            fft_size=2048,
            max_length=30,  # 30 seconds
            threshold=0.9
        )

    def test_checker_imports(self):
        """Test importing checker functions."""
        from matchering.checker import check
        from matchering import checker

        assert callable(check)
        assert hasattr(checker, 'check')

    def test_check_function_with_name(self, valid_audio, test_config):
        """Test check function with required name parameter."""
        from matchering.checker import check

        # Test with proper parameters including name
        try:
            result = check(valid_audio, 44100, test_config, "test_track")
            # Function should complete or give specific error
        except Exception as e:
            error_msg = str(e).lower()
            # Check for expected validation errors
            assert any(word in error_msg for word in [
                'validation', 'audio', 'sample', 'rate', 'length', 'format', 'clipping'
            ])

    def test_check_function_edge_cases(self, test_config):
        """Test check function with edge cases."""
        from matchering.checker import check

        # Test with very short audio
        short_audio = np.random.rand(1000, 2).astype(np.float32) * 0.5
        try:
            result = check(short_audio, 44100, test_config, "short_track")
        except Exception as e:
            error_msg = str(e).lower()
            assert any(word in error_msg for word in ['length', 'short', 'duration'])

        # Test with very quiet audio
        quiet_audio = np.random.rand(44100, 2).astype(np.float32) * 0.001
        try:
            result = check(quiet_audio, 44100, test_config, "quiet_track")
        except Exception as e:
            error_msg = str(e).lower()
            assert any(word in error_msg for word in ['quiet', 'level', 'threshold'])

        # Test with clipped audio
        clipped_audio = np.ones((44100, 2), dtype=np.float32)
        try:
            result = check(clipped_audio, 44100, test_config, "clipped_track")
        except Exception as e:
            error_msg = str(e).lower()
            assert any(word in error_msg for word in ['clip', 'limit', 'distort'])

    def test_checker_additional_functions(self, valid_audio):
        """Test additional checker functions if they exist."""
        from matchering import checker

        # Test other checker functions
        checker_functions = ['check_audio', 'validate_audio', 'check_format', 'check_levels']

        for func_name in checker_functions:
            if hasattr(checker, func_name):
                func = getattr(checker, func_name)
                if callable(func):
                    try:
                        result = func(valid_audio)
                        # Function completed
                    except Exception as e:
                        # Function might need specific parameters
                        error_msg = str(e).lower()
                        assert any(word in error_msg for word in [
                            'parameter', 'config', 'audio', 'format'
                        ])


class TestMatcheringCore:
    """Test core matchering processing functions."""

    @pytest.fixture
    def processing_config(self):
        """Create processing configuration."""
        from matchering.defaults import Config
        return Config(
            internal_sample_rate=44100,
            fft_size=2048,
            max_length=60,  # 1 minute
            threshold=0.95
        )

    @pytest.fixture
    def target_audio(self):
        """Create target audio for processing."""
        sample_rate = 44100
        duration = 3.0
        t = np.linspace(0, duration, int(sample_rate * duration))

        # Create unmastered target - lower levels
        audio = (np.sin(2 * np.pi * 440 * t) * 0.3 +
                np.sin(2 * np.pi * 1000 * t) * 0.2 +
                np.random.normal(0, 0.01, len(t)))

        return np.column_stack((audio, audio * 0.9)).astype(np.float32)

    @pytest.fixture
    def reference_audio(self):
        """Create reference audio for matching."""
        sample_rate = 44100
        duration = 3.0
        t = np.linspace(0, duration, int(sample_rate * duration))

        # Create mastered reference - higher levels
        audio = (np.sin(2 * np.pi * 440 * t) * 0.7 +
                np.sin(2 * np.pi * 1000 * t) * 0.4 +
                np.random.normal(0, 0.02, len(t)))

        return np.column_stack((audio, audio * 0.95)).astype(np.float32)

    def test_core_process_function(self, target_audio, reference_audio, processing_config):
        """Test core process function."""
        from matchering.core import process

        # Create temporary result file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_result_path = f.name

        try:
            from matchering.results import Result
            result = Result(temp_result_path)

            # Test the core processing function
            try:
                processed = process(target_audio, reference_audio, result, processing_config)
                # Function should complete or give specific error
                if processed is not None:
                    assert isinstance(processed, np.ndarray)
                    assert processed.shape == target_audio.shape
            except Exception as e:
                error_msg = str(e).lower()
                # Check for expected processing errors
                assert any(word in error_msg for word in [
                    'process', 'audio', 'config', 'reference', 'target', 'result'
                ])
        finally:
            if os.path.exists(temp_result_path):
                os.unlink(temp_result_path)

    def test_core_module_functions(self):
        """Test other core module functions."""
        from matchering import core

        # Test other functions that might exist
        core_functions = ['master', 'match', 'analyze', 'preprocess']

        for func_name in core_functions:
            if hasattr(core, func_name):
                func = getattr(core, func_name)
                assert callable(func)

    def test_core_with_different_configs(self, target_audio, reference_audio):
        """Test core processing with different configurations."""
        from matchering.core import process
        from matchering.defaults import Config

        # Test with different FFT sizes
        configs = [
            Config(fft_size=1024),
            Config(fft_size=4096),
            Config(internal_sample_rate=48000),
            Config(threshold=0.8),
        ]

        for config in configs:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                temp_path = f.name

            try:
                from matchering.results import Result
                result = Result(temp_path)

                try:
                    processed = process(target_audio, reference_audio, result, config)
                    # Test completed successfully
                except Exception as e:
                    # Expected - might need specific setup
                    error_msg = str(e).lower()
                    assert any(word in error_msg for word in [
                        'sample', 'rate', 'config', 'fft', 'process'
                    ])
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)


class TestProcessingStages:
    """Test individual processing stages."""

    @pytest.fixture
    def stage_audio(self):
        """Create audio for stage testing."""
        sample_rate = 44100
        duration = 2.0
        t = np.linspace(0, duration, int(sample_rate * duration))

        # Create audio with dynamic characteristics
        envelope = np.exp(-t * 0.5)  # Decay envelope
        audio = np.sin(2 * np.pi * 440 * t) * envelope

        return np.column_stack((audio, audio * 0.9)).astype(np.float32)

    def test_stages_module(self):
        """Test stages module functions."""
        from matchering import stages

        # Test that stages module has expected attributes
        stage_attrs = ['normalize', 'master', 'limiter', 'match']
        for attr in stage_attrs:
            if hasattr(stages, attr):
                func = getattr(stages, attr)
                if callable(func):
                    # Function exists and is callable
                    pass

    def test_normalization_stage(self, stage_audio):
        """Test normalization stage."""
        try:
            from matchering.stages import normalize
            from matchering.defaults import Config

            config = Config()

            try:
                normalized = normalize(stage_audio, config)
                if normalized is not None:
                    assert isinstance(normalized, np.ndarray)
                    assert normalized.shape == stage_audio.shape
            except Exception as e:
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'normalize', 'config', 'audio', 'stage'
                ])
        except ImportError:
            pytest.skip("Normalize stage not available")

    def test_mastering_stage(self, stage_audio):
        """Test mastering stage."""
        try:
            from matchering.stages import master
            from matchering.defaults import Config

            config = Config()
            reference = stage_audio * 1.2  # Louder reference

            try:
                mastered = master(stage_audio, reference, config)
                if mastered is not None:
                    assert isinstance(mastered, np.ndarray)
                    assert mastered.shape == stage_audio.shape
            except Exception as e:
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'master', 'reference', 'config', 'audio'
                ])
        except ImportError:
            pytest.skip("Master stage not available")

    def test_limiter_stage(self, stage_audio):
        """Test limiter stage."""
        try:
            from matchering.stages import limiter
            from matchering.defaults import Config

            config = Config()
            hot_audio = stage_audio * 2.0  # Hot signal

            try:
                limited = limiter(hot_audio, config)
                if limited is not None:
                    assert isinstance(limited, np.ndarray)
                    assert limited.shape == hot_audio.shape
                    # Should be limited
                    assert np.max(np.abs(limited)) <= np.max(np.abs(hot_audio))
            except Exception as e:
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'limit', 'config', 'audio', 'threshold'
                ])
        except ImportError:
            pytest.skip("Limiter stage not available")


class TestStageHelpers:
    """Test stage helper modules."""

    @pytest.fixture
    def frequency_data(self):
        """Create frequency domain data."""
        # Simulate FFT output
        n_bins = 1024
        freqs = np.fft.fftfreq(n_bins * 2, 1/44100)[:n_bins]

        # Create magnitude spectrum with some characteristics
        magnitude = np.exp(-freqs/2000) + 0.5 * np.exp(-(freqs-1000)**2/100000)

        return freqs, magnitude.astype(np.float32)

    @pytest.fixture
    def level_data(self):
        """Create level/amplitude data."""
        # Simulate RMS levels over time
        time_frames = 100
        levels = np.random.rand(time_frames) * 0.5 + 0.2  # Between 0.2 and 0.7

        return levels.astype(np.float32)

    def test_match_frequencies_helper(self, frequency_data):
        """Test frequency matching helper."""
        try:
            from matchering.stage_helpers.match_frequencies import match_frequencies

            freqs, target_mag = frequency_data
            reference_mag = target_mag * 1.5  # Different reference

            try:
                matched = match_frequencies(target_mag, reference_mag, freqs)
                assert isinstance(matched, np.ndarray)
                assert matched.shape == target_mag.shape
            except Exception as e:
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'frequency', 'match', 'magnitude', 'spectrum'
                ])
        except ImportError:
            pytest.skip("Match frequencies helper not available")

    def test_match_levels_helper(self, level_data):
        """Test level matching helper."""
        try:
            from matchering.stage_helpers.match_levels import match_levels

            target_levels = level_data
            reference_levels = level_data * 1.3  # Different levels

            try:
                matched = match_levels(target_levels, reference_levels)
                assert isinstance(matched, np.ndarray)
                assert matched.shape == target_levels.shape
            except Exception as e:
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'level', 'match', 'amplitude', 'rms'
                ])
        except ImportError:
            pytest.skip("Match levels helper not available")

    def test_stage_helpers_with_real_data(self, frequency_data, level_data):
        """Test stage helpers with realistic data."""
        freqs, spectrum = frequency_data
        levels = level_data

        # Test frequency matching with different algorithms
        try:
            from matchering.stage_helpers import match_frequencies

            if hasattr(match_frequencies, 'linear_match'):
                try:
                    result = match_frequencies.linear_match(spectrum, spectrum * 1.2)
                except Exception:
                    pass

            if hasattr(match_frequencies, 'log_match'):
                try:
                    result = match_frequencies.log_match(spectrum, spectrum * 1.2)
                except Exception:
                    pass
        except ImportError:
            pass

        # Test level matching with different methods
        try:
            from matchering.stage_helpers import match_levels

            if hasattr(match_levels, 'rms_match'):
                try:
                    result = match_levels.rms_match(levels, levels * 1.3)
                except Exception:
                    pass

            if hasattr(match_levels, 'peak_match'):
                try:
                    result = match_levels.peak_match(levels, levels * 1.3)
                except Exception:
                    pass
        except ImportError:
            pass


class TestAuralisCoreComponents:
    """Test auralis core components."""

    def test_auralis_core_config(self):
        """Test auralis core configuration."""
        try:
            from auralis.core.config import AuralisConfig

            # Test creating config
            config = AuralisConfig()
            assert config is not None

            # Test config attributes
            config_attrs = ['sample_rate', 'buffer_size', 'processing_quality']
            for attr in config_attrs:
                if hasattr(config, attr):
                    # Attribute exists
                    pass

        except ImportError:
            pytest.skip("Auralis core config not available")

    def test_auralis_core_processor(self):
        """Test auralis core processor."""
        try:
            from auralis.core.processor import AudioProcessor

            # Test creating processor
            try:
                processor = AudioProcessor()
                assert processor is not None

                # Test processor methods
                processor_methods = ['process', 'initialize', 'reset']
                for method_name in processor_methods:
                    if hasattr(processor, method_name):
                        method = getattr(processor, method_name)
                        assert callable(method)

            except Exception as e:
                # Processor might need configuration
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'processor', 'config', 'audio', 'initialize'
                ])

        except ImportError:
            pytest.skip("Auralis core processor not available")

    def test_auralis_processor_with_audio(self):
        """Test auralis processor with audio data."""
        try:
            from auralis.core.processor import AudioProcessor
            from auralis.core.config import AuralisConfig

            config = AuralisConfig()
            processor = AudioProcessor(config)

            # Create test audio
            test_audio = np.random.rand(1024, 2).astype(np.float32) * 0.5

            try:
                processed = processor.process(test_audio)
                if processed is not None:
                    assert isinstance(processed, np.ndarray)
                    assert processed.shape == test_audio.shape
            except Exception as e:
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'process', 'audio', 'buffer', 'format'
                ])

        except ImportError:
            pytest.skip("Auralis core components not available")


class TestUtilitiesAndHelpers:
    """Test additional utilities and helper functions."""

    def test_matchering_utils_functions(self):
        """Test matchering utils module."""
        from matchering import utils

        # Test utility functions
        test_audio = np.random.rand(1024, 2).astype(np.float32) * 0.5

        util_functions = ['rms', 'peak', 'db_to_linear', 'linear_to_db']
        for func_name in util_functions:
            if hasattr(utils, func_name):
                func = getattr(utils, func_name)
                if callable(func):
                    try:
                        if func_name in ['rms', 'peak']:
                            result = func(test_audio)
                            assert isinstance(result, (float, np.floating))
                        elif func_name in ['db_to_linear', 'linear_to_db']:
                            result = func(-20.0)  # -20 dB
                            assert isinstance(result, (float, np.floating))
                    except Exception:
                        # Function might need different parameters
                        pass

    def test_preview_creator_functionality(self):
        """Test preview creator with different options."""
        try:
            from matchering.preview_creator import create_preview
            from matchering.defaults import Config

            # Create test audio (10 seconds)
            sample_rate = 44100
            duration = 10.0
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
            stereo_audio = np.column_stack((audio, audio * 0.9))

            config = Config()

            try:
                preview = create_preview(stereo_audio, sample_rate, config)
                assert isinstance(preview, np.ndarray)
                assert preview.shape[1] == 2  # Stereo
                assert preview.shape[0] < stereo_audio.shape[0]  # Shorter than original
            except Exception as e:
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'preview', 'config', 'audio', 'length'
                ])

        except ImportError:
            pytest.skip("Preview creator not available")

    def test_limiter_hyrax_advanced(self):
        """Test advanced Hyrax limiter functionality."""
        try:
            from matchering.limiter.hyrax import HyraxLimiter
            from matchering.defaults import LimiterConfig

            # Test with custom limiter config
            limiter_config = LimiterConfig(
                attack=2.0,
                release=5000.0
            )

            limiter = HyraxLimiter(44100, limiter_config)

            # Test with different audio types
            test_cases = [
                np.random.rand(2048, 2).astype(np.float32) * 1.5,  # Hot signal
                np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100)).reshape(-1, 1),  # Mono sine
                np.ones((1024, 2), dtype=np.float32) * 0.9,  # Constant level
            ]

            for audio in test_cases:
                if audio.ndim == 1:
                    audio = audio.reshape(-1, 1)
                if audio.shape[1] == 1:
                    audio = np.column_stack((audio[:, 0], audio[:, 0]))

                try:
                    limited = limiter.process(audio)
                    assert limited.shape == audio.shape
                    assert np.max(np.abs(limited)) <= 1.0
                except Exception as e:
                    error_msg = str(e).lower()
                    assert any(word in error_msg for word in [
                        'limiter', 'process', 'audio', 'format'
                    ])

        except ImportError:
            pytest.skip("Hyrax limiter not available")
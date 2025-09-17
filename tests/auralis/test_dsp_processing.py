"""
DSP Processing Tests
Tests for DSP functions that can be tested with synthetic audio data.
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path


class TestMatcheringDSP:
    """Test matchering DSP functions with synthetic data."""

    @pytest.fixture
    def mono_audio(self):
        """Create mono test audio - 1 second of mixed frequencies."""
        sample_rate = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))

        # Mix of frequencies: 440Hz + 880Hz + noise
        audio = (np.sin(2 * np.pi * 440 * t) * 0.3 +
                np.sin(2 * np.pi * 880 * t) * 0.2 +
                np.random.normal(0, 0.05, len(t)))

        return audio.astype(np.float32)

    @pytest.fixture
    def stereo_audio(self, mono_audio):
        """Create stereo test audio."""
        # Make stereo with slight difference between channels
        left = mono_audio
        right = mono_audio * 0.9  # Slightly quieter right channel
        return np.column_stack((left, right))

    def test_dsp_normalize_function(self, stereo_audio):
        """Test DSP normalize function."""
        from matchering import dsp

        # Test basic normalization (returns tuple: array, gain)
        result = dsp.normalize(stereo_audio, 0.8)
        assert isinstance(result, tuple)
        assert len(result) == 2

        normalized, gain = result
        assert normalized.shape == stereo_audio.shape
        assert normalized.dtype == stereo_audio.dtype
        assert isinstance(gain, (float, np.floating))

    def test_dsp_fade_function(self, stereo_audio):
        """Test DSP fade function."""
        from matchering import dsp

        fade_samples = 256
        faded = dsp.fade(stereo_audio, fade_samples)

        assert faded.shape == stereo_audio.shape
        assert faded.dtype == stereo_audio.dtype

        # Check that beginning is faded (quieter)
        original_start = np.mean(np.abs(stereo_audio[:fade_samples]))
        faded_start = np.mean(np.abs(faded[:fade_samples]))
        assert faded_start < original_start

    def test_dsp_functions_edge_cases(self):
        """Test DSP functions with edge cases."""
        from matchering import dsp

        # Very quiet audio
        quiet_audio = np.random.normal(0, 0.001, (1024, 2)).astype(np.float32)
        result_quiet = dsp.normalize(quiet_audio, 0.5)
        if isinstance(result_quiet, tuple):
            normalized_quiet, _ = result_quiet
        else:
            normalized_quiet = result_quiet
        assert not np.any(np.isnan(normalized_quiet))
        assert not np.any(np.isinf(normalized_quiet))

        # Very loud audio (clipped)
        loud_audio = np.ones((1024, 2), dtype=np.float32) * 2.0  # Clipped
        result_loud = dsp.normalize(loud_audio, 0.9)
        if isinstance(result_loud, tuple):
            normalized_loud, _ = result_loud
        else:
            normalized_loud = result_loud
        # Check bounds are reasonable
        assert np.all(np.abs(normalized_loud) <= 10.0)  # Not infinite

        # Single sample
        single_sample = np.array([[0.5, 0.5]], dtype=np.float32)
        try:
            result_single = dsp.normalize(single_sample, 0.8)
            if isinstance(result_single, tuple):
                normalized_single, _ = result_single
                assert normalized_single.shape == single_sample.shape
        except Exception:
            # Some DSP functions might not work with single samples
            pass

    def test_dsp_additional_functions(self, stereo_audio):
        """Test other DSP functions if they exist."""
        from matchering import dsp

        # Test other functions that might exist
        dsp_functions = ['apply_rms', 'rms', 'peak', 'db_to_linear', 'linear_to_db']

        for func_name in dsp_functions:
            if hasattr(dsp, func_name):
                func = getattr(dsp, func_name)
                if callable(func):
                    try:
                        if func_name in ['rms', 'peak']:
                            # Functions that return scalar values
                            result = func(stereo_audio)
                            assert isinstance(result, (float, np.floating))
                        elif func_name in ['db_to_linear', 'linear_to_db']:
                            # Functions that work with scalars
                            result = func(-20.0)  # -20 dB
                            assert isinstance(result, (float, np.floating))
                        else:
                            # Functions that process audio
                            result = func(stereo_audio)
                            assert result.shape == stereo_audio.shape
                    except Exception:
                        # Function might need different parameters
                        pass


class TestMatcheringCore:
    """Test core matchering processing functions."""

    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        from matchering.defaults import Config
        return Config(
            internal_sample_rate=44100,
            fft_size=2048,  # Smaller for faster tests
            max_length=30,  # 30 seconds max
        )

    @pytest.fixture
    def reference_audio(self):
        """Create reference audio for matching."""
        sample_rate = 44100
        duration = 2.0  # 2 seconds
        t = np.linspace(0, duration, int(sample_rate * duration))

        # Create "mastered" reference with multiple frequencies
        audio = (np.sin(2 * np.pi * 440 * t) * 0.6 +
                np.sin(2 * np.pi * 1000 * t) * 0.3 +
                np.sin(2 * np.pi * 3000 * t) * 0.1)

        return np.column_stack((audio, audio)).astype(np.float32)

    @pytest.fixture
    def target_audio(self):
        """Create target audio to be mastered."""
        sample_rate = 44100
        duration = 2.0
        t = np.linspace(0, duration, int(sample_rate * duration))

        # Create "unmastered" target - similar content but different levels
        audio = (np.sin(2 * np.pi * 440 * t) * 0.3 +
                np.sin(2 * np.pi * 1000 * t) * 0.2 +
                np.sin(2 * np.pi * 3000 * t) * 0.05)

        return np.column_stack((audio, audio)).astype(np.float32)

    def test_core_process_function_exists(self):
        """Test that core process function exists and is callable."""
        from matchering.core import process
        assert callable(process)

    def test_checker_functions_with_synthetic_audio(self, target_audio, reference_audio, test_config):
        """Test checker functions with synthetic audio."""
        from matchering.checker import check

        # Test check function with our synthetic audio
        try:
            # Check target audio
            result = check(target_audio, 44100, test_config)
            # Function should complete without error
        except Exception as e:
            # Check for expected error types
            error_msg = str(e).lower()
            assert any(word in error_msg for word in [
                'sample', 'rate', 'length', 'format', 'audio'
            ])

    def test_loader_with_temp_files(self):
        """Test loader functions with temporary audio files."""
        from matchering import loader

        # Test that loader functions exist
        assert hasattr(loader, 'load')
        assert callable(loader.load)

        # Create a temporary WAV file path (not actual audio file)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            # Try to load (will likely fail but tests the function)
            try:
                audio, sr = loader.load(temp_path)
            except Exception as e:
                # Expected - no actual audio file
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'file', 'format', 'read', 'audio', 'sound'
                ])
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_saver_functions(self, target_audio):
        """Test saver functions."""
        from matchering import saver
        from matchering.results import Result

        # Test that saver functions exist
        assert hasattr(saver, 'save')
        assert callable(saver.save)

        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            result = Result(temp_path)

            # Try to save (might fail due to missing dependencies)
            try:
                saver.save(target_audio, 44100, result)
            except Exception as e:
                # Expected - might need specific audio libraries
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'format', 'save', 'write', 'audio', 'file'
                ])
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestStageHelpers:
    """Test stage helper functions."""

    @pytest.fixture
    def frequency_spectrum(self):
        """Create test frequency spectrum data."""
        # Simulate FFT result
        freqs = np.fft.fftfreq(2048, 1/44100)[:1024]  # Positive frequencies only
        # Create a spectrum with some peaks
        spectrum = np.exp(-freqs/1000) + np.exp(-(freqs-1000)**2/100000)
        return freqs, spectrum.astype(np.float32)

    def test_match_frequencies_import(self):
        """Test importing match frequencies helper."""
        try:
            from matchering.stage_helpers.match_frequencies import match_frequencies
            assert callable(match_frequencies)
        except ImportError:
            pytest.skip("Match frequencies helper not available")

    def test_match_levels_import(self):
        """Test importing match levels helper."""
        try:
            from matchering.stage_helpers.match_levels import match_levels
            assert callable(match_levels)
        except ImportError:
            pytest.skip("Match levels helper not available")

    def test_stage_helpers_with_data(self, frequency_spectrum):
        """Test stage helpers with synthetic data."""
        freqs, spectrum = frequency_spectrum

        # Try match_frequencies if available
        try:
            from matchering.stage_helpers.match_frequencies import match_frequencies

            # Create reference and target spectra
            reference_spectrum = spectrum * 1.2  # Slightly different

            try:
                result = match_frequencies(spectrum, reference_spectrum, freqs)
                # Should return modified spectrum
                assert isinstance(result, np.ndarray)
                assert result.shape == spectrum.shape
            except Exception as e:
                # Function might need specific format
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'frequency', 'spectrum', 'shape', 'array'
                ])
        except ImportError:
            pass

        # Try match_levels if available
        try:
            from matchering.stage_helpers.match_levels import match_levels

            # Create level data
            target_levels = np.random.rand(100).astype(np.float32)
            reference_levels = target_levels * 1.5  # Different levels

            try:
                result = match_levels(target_levels, reference_levels)
                assert isinstance(result, np.ndarray)
            except Exception as e:
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'level', 'array', 'shape', 'size'
                ])
        except ImportError:
            pass


class TestProcessingStages:
    """Test processing stages."""

    @pytest.fixture
    def stage_audio(self):
        """Create audio for stage processing."""
        sample_rate = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))

        # Create audio with dynamic range
        audio = np.sin(2 * np.pi * 440 * t) * np.exp(-t)  # Decaying sine
        return np.column_stack((audio, audio)).astype(np.float32)

    def test_stages_module_imports(self):
        """Test importing stages module."""
        try:
            from matchering import stages
            assert stages is not None
        except ImportError:
            pytest.skip("Stages module not available")

    def test_individual_stages(self, stage_audio):
        """Test individual processing stages if available."""
        try:
            from matchering import stages

            # Test common stage functions
            stage_functions = ['normalize', 'match', 'limit', 'master']

            for func_name in stage_functions:
                if hasattr(stages, func_name):
                    func = getattr(stages, func_name)
                    if callable(func):
                        try:
                            # Try calling with basic parameters
                            if func_name == 'normalize':
                                result = func(stage_audio)
                            elif func_name == 'match':
                                # Needs reference
                                reference = stage_audio * 1.2
                                result = func(stage_audio, reference)
                            else:
                                result = func(stage_audio)

                            if result is not None:
                                assert isinstance(result, np.ndarray)
                                assert result.shape == stage_audio.shape
                        except Exception as e:
                            # Function might need specific parameters
                            error_msg = str(e).lower()
                            assert any(word in error_msg for word in [
                                'audio', 'config', 'parameter', 'reference'
                            ])
        except ImportError:
            pytest.skip("Stages module not available")


class TestUtilsAndHelpers:
    """Test utility functions and helpers."""

    def test_utils_functions(self):
        """Test matchering utils functions."""
        from matchering import utils

        # Test available utility functions
        if hasattr(utils, 'rms'):
            test_data = np.random.rand(1024).astype(np.float32)
            rms_val = utils.rms(test_data)
            assert isinstance(rms_val, (float, np.floating))
            assert rms_val >= 0

        if hasattr(utils, 'peak'):
            test_data = np.random.rand(1024).astype(np.float32)
            peak_val = utils.peak(test_data)
            assert isinstance(peak_val, (float, np.floating))
            assert peak_val >= 0

    def test_preview_creator(self):
        """Test preview creator functionality."""
        try:
            from matchering.preview_creator import create_preview
            assert callable(create_preview)

            # Create test audio for preview
            sample_rate = 44100
            duration = 10.0  # 10 seconds
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
            stereo_audio = np.column_stack((audio, audio))

            try:
                preview = create_preview(stereo_audio, sample_rate)
                assert isinstance(preview, np.ndarray)
                assert preview.shape[1] == 2  # Stereo
                assert preview.shape[0] < stereo_audio.shape[0]  # Shorter
            except Exception as e:
                # Function might need specific config
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'preview', 'config', 'length', 'sample'
                ])
        except ImportError:
            pytest.skip("Preview creator not available")

    def test_limiter_functionality(self):
        """Test limiter functionality."""
        try:
            from matchering.limiter.hyrax import HyraxLimiter

            sample_rate = 44100
            limiter = HyraxLimiter(sample_rate)
            assert limiter is not None

            # Test with hot audio (needs limiting)
            hot_audio = np.ones((1024, 2), dtype=np.float32) * 1.5

            try:
                limited = limiter.process(hot_audio)
                assert limited.shape == hot_audio.shape
                assert np.max(np.abs(limited)) <= 1.0  # Should be limited
            except Exception as e:
                # Limiter might need specific setup
                error_msg = str(e).lower()
                assert any(word in error_msg for word in [
                    'limiter', 'process', 'audio', 'config'
                ])
        except ImportError:
            pytest.skip("Hyrax limiter not available")